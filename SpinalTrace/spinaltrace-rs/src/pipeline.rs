//! SPINALTRACE: the trace pipeline shared by the CLI and the GUI (ChiselTrace duplicated it in both):
//! read PDG -> replay VCD -> export DPDG -> convert to source statements -> attach simulation values.
use std::{collections::BTreeMap, fs::File, io::BufReader, path::PathBuf};

use anyhow::{Context, Result};
use serde::Deserialize;

use crate::{
    conversion::{dpdg_make_exportable, pdg_convert_to_source},
    graphbuilder::{CriterionType, GraphBuilder, GraphProcessingType, ResetKind, StopAt, TraceSignals},
    pdg_spec::{ExportablePDG, PDGSpec, PDGSpecEdgeKind},
    sim_data_injection::{inject_raw_values, TywavesInterface},
};

#[derive(Debug, Clone)]
pub struct TraceRequest {
    pub pdg_path: PathBuf,
    pub vcd_path: PathBuf,
    /// HGLDD directory for typed (Tywaves) values; without it raw VCD values are attached.
    pub hgldd_path: Option<PathBuf>,
    pub criterion: CriterionType,
    pub top_module: Option<String>,
    pub extra_scopes: Option<Vec<String>>,
    pub clock: Option<String>,
    pub reset: Option<String>,
    pub no_reset: bool,
    pub reset_active_low: Option<bool>,
    pub reset_kind: Option<ResetKind>,
    pub max_timesteps: Option<i64>,
    pub stop_at: StopAt,
    pub processing_type: GraphProcessingType,
    /// false = keep the netlist-level graph (ChiselTrace `--fir true`)
    pub convert_to_source: bool,
    /// attach raw VCD values when no HGLDD is given
    pub raw_values: bool,
}

impl TraceRequest {
    pub fn new(pdg_path: impl Into<PathBuf>, vcd_path: impl Into<PathBuf>, criterion: CriterionType) -> Self {
        TraceRequest {
            pdg_path: pdg_path.into(), vcd_path: vcd_path.into(), hgldd_path: None, criterion,
            top_module: None, extra_scopes: None, clock: None, reset: None, no_reset: false,
            reset_active_low: None, reset_kind: None, max_timesteps: None, stop_at: StopAt::End,
            processing_type: GraphProcessingType::Normal, convert_to_source: true, raw_values: true,
        }
    }
}

pub fn read_pdg(path: &PathBuf) -> Result<PDGSpec> {
    let reader = BufReader::new(File::open(path).with_context(|| format!("cannot open PDG {}", path.display()))?);
    let mut deser = serde_json::Deserializer::from_reader(reader);
    deser.disable_recursion_limit();
    Ok(PDGSpec::deserialize(&mut deser).with_context(|| format!("cannot parse PDG {}", path.display()))?)
}

pub fn parse_reset_kind(s: &str) -> Result<ResetKind, String> {
    match s.to_ascii_lowercase().as_str() {
        "async" => Ok(ResetKind::Async),
        "sync" => Ok(ResetKind::Sync),
        "none" | "boot" => Ok(ResetKind::None),
        other => Err(format!("unknown reset kind '{}' (async, sync, none)", other)),
    }
}

/// Signal names / layout: explicit options first, then the PDG metadata, then ChiselTrace defaults.
pub fn resolve_signals(pdg: &PDGSpec, req: &TraceRequest) -> (TraceSignals, String) {
    let meta = pdg.spinaltrace.as_ref();
    let top = req.top_module.clone()
        .or_else(|| meta.map(|m| m.toplevel.clone()).filter(|t| !t.is_empty()))
        .unwrap_or_default();
    let cd = meta.and_then(|m| m.clock_domains.iter().max_by_key(|c| c.registers));
    let extra_scopes = req.extra_scopes.clone()
        .or_else(|| meta.map(|m| m.extra_scopes.clone()).filter(|s| !s.is_empty()))
        .unwrap_or_else(|| if top.is_empty() { vec!["TOP".into()] } else { vec!["TOP".into(), top.clone()] });
    let (def_clock, def_reset, def_low, def_kind) = match (meta, cd) {
        (Some(_), Some(cd)) => (cd.clock.clone(), cd.reset.clone(), cd.reset_active_low,
            match cd.reset_kind.as_str() { "SYNC" => ResetKind::Sync, "BOOT" => ResetKind::None, _ => ResetKind::Async }),
        (Some(_), None) => ("clk".into(), Some("reset".into()), false, ResetKind::Async),
        (None, _) => ("clock".into(), Some("reset".into()), false, ResetKind::Sync),
    };
    let reset = if req.no_reset { None } else { req.reset.clone().or(def_reset) };
    let kind = if reset.is_none() { ResetKind::None } else { req.reset_kind.unwrap_or(def_kind) };
    (TraceSignals {
        extra_scopes,
        clock: req.clock.clone().unwrap_or(def_clock),
        reset,
        reset_active_low: req.reset_active_low.unwrap_or(def_low),
        reset_kind: kind,
        stop_at: req.stop_at,
    }, top)
}

/// `signal:` criteria may use the RTL path (`io_result`, `sub.io_y`) or the Spinal/HGL path
/// (`io.result`, `sub.io.y`).
pub fn resolve_criterion(pdg: &PDGSpec, c: &CriterionType) -> CriterionType {
    match c {
        CriterionType::Signal(s) => {
            if pdg.vertices.iter().any(|v| v.assigns_to.as_deref() == Some(s.as_str())) {
                return c.clone();
            }
            let by_hgl = pdg.vertices.iter().find(|v| v.related_signal.as_ref().map_or(false, |r| {
                let full = if r.field_path.is_empty() { r.signal_path.clone() } else { format!("{}.{}", r.signal_path, r.field_path) };
                full == *s
            }) && v.assigns_to.is_some());
            match by_hgl {
                Some(v) => CriterionType::Signal(v.assigns_to.clone().unwrap()),
                None => c.clone(),
            }
        }
        _ => c.clone(),
    }
}

/// Clock-domain and extraction warnings stored in the PDG.
pub fn design_warnings(pdg: &PDGSpec) -> Vec<String> {
    let mut out = vec![];
    if let Some(m) = &pdg.spinaltrace {
        if m.clock_domains.len() > 1 {
            out.push(format!(
                "the design has {} clock domains ({}); SpinalTrace replays every register on the clock of the \
                 busiest domain, so dependencies through the other domains are timed incorrectly",
                m.clock_domains.len(),
                m.clock_domains.iter().map(|c| c.clock.as_str()).collect::<Vec<_>>().join(", ")));
        }
        out.extend(m.warnings.iter().cloned());
    }
    out
}

pub fn trace(req: &TraceRequest) -> Result<ExportablePDG> {
    let pdg = read_pdg(&req.pdg_path)?;
    for w in design_warnings(&pdg) {
        eprintln!("warning: {}", w);
    }
    let (signals, top) = resolve_signals(&pdg, req);
    let criterion = resolve_criterion(&pdg, &req.criterion);
    let extra_scopes = signals.extra_scopes.clone();
    let clock = signals.clock.clone();

    let reset_disabled = req.no_reset && pdg.spinaltrace.as_ref().map_or(false,
        |m| m.clock_domains.iter().any(|c| c.reset.is_some()));
    let mut builder = GraphBuilder::with_signals(&req.vcd_path, signals, pdg)?;
    let dpdg = builder.process(&criterion, req.max_timesteps, req.processing_type)?;
    let mut dpdg = dpdg_make_exportable(dpdg);
    dpdg.accuracy = builder.accuracy.clone();
    if reset_disabled {
        dpdg.accuracy.report("incomplete", "Reset replay was disabled for a design with reset.");
    }
    if matches!(req.processing_type, GraphProcessingType::DataOnly) {
        dpdg.accuracy.report("incomplete", "Data-only tracing omits control and index causes.");
    }
    let mut converted = if req.convert_to_source { pdg_convert_to_source(dpdg, false, true) } else { dpdg };

    let mut typed = false;
    if let Some(hgldd) = &req.hgldd_path {
        let attempt = (|| -> Result<()> {
            let tywaves = TywavesInterface::with_clock(hgldd, extra_scopes.clone(), &top, &clock)?;
            let tywaves_vcd = tywaves.vcd_rewrite(&req.vcd_path)?;
            tywaves.inject_sim_data(&mut converted, &tywaves_vcd)?;
            Ok(())
        })();
        match attempt {
            Ok(()) => typed = true,
            Err(e) => eprintln!("warning: typed (HGLDD) values unavailable, falling back to raw VCD values: {:#}", e),
        }
    }
    if !typed && req.raw_values {
        if let Err(e) = inject_raw_values(&mut converted, &req.vcd_path, &extra_scopes, &clock) {
            eprintln!("warning: could not attach raw VCD values: {:#}", e);
        }
    }
    Ok(converted)
}

/// Human-readable digest of a (source-level) DPDG: one line per node, newest first, with the
/// kinds of its outgoing dependency edges.
pub fn summary(pdg: &ExportablePDG) -> String {
    let mut by_time: BTreeMap<std::cmp::Reverse<i64>, Vec<usize>> = BTreeMap::new();
    for (i, v) in pdg.vertices.iter().enumerate() {
        by_time.entry(std::cmp::Reverse(v.timestamp)).or_default().push(i);
    }
    let mut out = format!("Trace accuracy: {}\n", pdg.accuracy.status);
    for reason in &pdg.accuracy.reasons { out += &format!("- {}\n", reason); }
    out += &format!("{} nodes, {} edges\n", pdg.vertices.len(), pdg.edges.len());
    let dropped = crate::conversion::dropped_probe_edges();
    if dropped > 0 {
        out += &format!("{} edge(s) into probe vertices without a source were dropped\n", dropped);
    }
    for (_, idxs) in by_time {
        for i in idxs {
            let v = &pdg.vertices[i];
            let file = v.file.rsplit('/').next().unwrap_or("");
            let mut deps: Vec<String> = pdg.edges.iter().filter(|e| e.from as usize == i).map(|e| {
                let k = match e.kind { PDGSpecEdgeKind::Data => "data", PDGSpecEdgeKind::Conditional => "cond",
                    PDGSpecEdgeKind::Index => "index", PDGSpecEdgeKind::Declaration => "decl" };
                let t = &pdg.vertices[e.to as usize];
                format!("{}->{}:{}@t{}", k, t.file.rsplit('/').next().unwrap_or(""), t.line, t.timestamp)
            }).collect();
            deps.sort();
            out += &format!("t={:<4} {}:{:<5} {:<12?} {:<36} {:<24} {}\n", v.timestamp, file, v.line, v.kind, v.name,
                v.sim_data.clone().unwrap_or_default(), deps.join(" "));
        }
    }
    out
}
