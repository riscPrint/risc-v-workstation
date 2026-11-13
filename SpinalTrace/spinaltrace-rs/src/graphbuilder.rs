// Dynamic PDG builder. Forked from chiseltrace-rs (jarlb/chiseltrace f4bf63a, Apache-2.0).
// SpinalTrace patches are marked with "SPINALTRACE:" and listed in PORTING_NOTES.md.
use std::{cell::RefCell, collections::{HashMap, HashSet}, path::Path, rc::Rc};
use serde::Serialize;
use vcd::{Command as Command, IdCode};
use anyhow::Result;

use crate::{pdg_spec::{CFGCaseKey, CFGSpecStatement, PDGSpec, PDGSpecCondition, PDGSpecEdge, PDGSpecEdgeKind, PDGSpecNode, PDGSpecNodeKind}, errors::Error};

/// SPINALTRACE: how register init values are applied.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum ResetKind {
    /// Reset acts immediately while asserted (Spinal default ASYNC).
    Async,
    /// Reset is sampled on the clock edge (Spinal SYNC).
    Sync,
    /// No reset signal: init values only apply at t=0 (Spinal BOOT / no reset).
    None,
}

/// SPINALTRACE: where to stop replaying the VCD.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum StopAt {
    End,
    /// Stop after cycle n (0 = before the first rising edge). Register values are those *during* cycle n.
    Cycle(i64),
    /// Stop in the cycle that contains this VCD time.
    Time(u64),
}

/// SPINALTRACE: signal names and VCD layout (ChiselTrace hardcodes `clock`, `reset` and the scopes).
#[derive(Debug, Clone)]
pub struct TraceSignals {
    pub extra_scopes: Vec<String>,
    pub clock: String,
    pub reset: Option<String>,
    pub reset_active_low: bool,
    pub reset_kind: ResetKind,
    pub stop_at: StopAt,
}

impl TraceSignals {
    /// ChiselTrace defaults.
    pub fn chiseltrace(extra_scopes: Vec<String>) -> Self {
        TraceSignals { extra_scopes, clock: "clock".into(), reset: Some("reset".into()), reset_active_low: false,
            reset_kind: ResetKind::Sync, stop_at: StopAt::End }
    }
}

pub struct GraphBuilder {
    pub accuracy: crate::pdg_spec::TraceAccuracy,
    reader: VcdReader,
    pdg: PDGSpec,
    linked_nodes: Vec<Rc<RefCell<PDGNode>>>,
    // This struct should contain some kind of state.
    dependency_state: HashMap<String, ProviderSet>,
    signals: TraceSignals,
}

type DynRef = Rc<RefCell<DynPDGNode>>;

/// SPINALTRACE: the active providers of one signal. ChiselTrace keeps a single provider per signal;
/// Spinal allows partial (bit / range) assignments, so a full assignment replaces everything while a
/// partial one only replaces the provider with the same range key.
#[derive(Clone, Default)]
struct ProviderSet {
    full: Option<DynRef>,
    partial: Vec<(String, DynRef)>,
}

/// Dynamic-index partial writes are kept, but only the most recent ones.
const MAX_DYN_PARTIALS: usize = 16;

impl ProviderSet {
    fn assign(&mut self, range: Option<&String>, node: DynRef) {
        match range {
            None => {
                self.full = Some(node);
                self.partial.clear();
            }
            Some(r) => {
                if r != "dyn" {
                    self.partial.retain(|(k, _)| k != r);
                } else if self.partial.iter().filter(|(k, _)| k == "dyn").count() >= MAX_DYN_PARTIALS {
                    if let Some(pos) = self.partial.iter().position(|(k, _)| k == "dyn") {
                        self.partial.remove(pos);
                    }
                }
                self.partial.push((r.clone(), node));
            }
        }
    }

    fn all(&self) -> impl Iterator<Item = &DynRef> {
        self.full.iter().chain(self.partial.iter().map(|(_, n)| n))
    }

    fn latest(&self) -> Option<&DynRef> {
        self.partial.last().map(|(_, n)| n).or(self.full.as_ref())
    }
}

struct VcdReader {
    parser: crate::vcd_input::Parser,
    extra_scopes: Vec<String>,
    header: vcd::Header,
    clock: vcd::IdCode,
    reset: Option<vcd::IdCode>,
    reset_active_value: char,
    clock_val: vcd::Value,
    /// SPINALTRACE: every VCD variable the engine reads (predicates, probes, case-key signals).
    watched: HashMap<IdCode, Vec<String>>,
    /// Committed (pre-edge) values, MSB first, as '0'/'1'/'x'/'z' strings.
    values: HashMap<String, String>,
    pending: Vec<(IdCode, String)>,
    reset_value: char,
    /// Reset was active at some point during the current cycle.
    reset_seen: bool,
    /// VCD time of the rising edge that ended the last read cycle.
    last_edge_time: Option<u64>,
    block_time: u64,
}

#[derive(Debug)]
struct PDGNode {
    inner: Rc<PDGSpecNode>,
    provides: Vec<(Rc<RefCell<PDGNode>>, PDGSpecEdge)>,
    dependencies: Vec<(Rc<RefCell<PDGNode>>, PDGSpecEdge)>
}

// A word of warning: if there are somehow cycles in the graph, the refcounted pointers WILL leak memory
// This shouldn't happen though.
#[derive(Debug, Serialize)]
pub struct DynPDGNode {
    pub inner: Rc<PDGSpecNode>,
    pub timestamp: i64,
    pub dependencies: Vec<(Rc<RefCell<DynPDGNode>>, PDGSpecEdgeKind)>
}

#[derive(Debug, Clone)]
pub enum CriterionType {
    Statement(String),
    Signal(String),
    /// SPINALTRACE: latest activated statement on a source line, `line:<file suffix>:<line>`.
    Line(String, u32),
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum GraphProcessingType {
    Normal, // The regular ChiselTrace options with data / control flow / index tracing
    DataOnly, // An option for data only tracing, results in smaller graphs
    Full // Also trace statement definitions. This is useful for exporting a full dynamic slice
}

fn condition_satisfied(cond: &Option<PDGSpecCondition>, values: &HashMap<String, String>) -> bool {
    if let Some(conds) = cond {
        conds.probe_name.iter().zip(&conds.probe_value).all(|(probe, required_value)| {
            values.get(probe).and_then(|v| bits_to_u64(v)).map_or(false, |v| v == *required_value)
        })
    } else {
        true
    }
}

/// Unsigned value of a bit string; None if it holds x/z or does not fit in 64 bits.
pub fn bits_to_u64(bits: &str) -> Option<u64> {
    let trimmed = bits.trim_start_matches('0');
    if trimmed.len() > 64 {
        return None;
    }
    let mut val: u64 = 0;
    for c in trimmed.chars() {
        val = (val << 1) | match c { '0' => 0, '1' => 1, _ => return None };
    }
    Some(val)
}

fn is_truthy(bits: &str) -> bool {
    !bits.is_empty() && bits.chars().all(|c| c == '0' || c == '1') && bits.contains('1')
}

fn pad_to(bits: &str, width: usize) -> String {
    if bits.len() >= width { bits[bits.len() - width..].to_string() } else {
        // VCD drops leading zeros; a leading x/z extends, anything else extends with 0.
        let fill = match bits.chars().next() { Some('x') => 'x', Some('z') => 'z', _ => '0' };
        std::iter::repeat(fill).take(width - bits.len()).chain(bits.chars()).collect()
    }
}

fn key_matches(key: &CFGCaseKey, value: &str, values: &HashMap<String, String>) -> bool {
    if let Some(pattern) = &key.pattern {
        let v = pad_to(value, pattern.len());
        pattern.chars().zip(v.chars()).all(|(p, b)| p == '-' || (p == b && (b == '0' || b == '1')))
    } else if let Some(sig) = &key.signal {
        match values.get(sig) {
            Some(other) => {
                let w = other.len().max(value.len());
                let (a, b) = (pad_to(value, w), pad_to(other, w));
                a == b && a.chars().all(|c| c == '0' || c == '1')
            }
            None => false,
        }
    } else {
        false
    }
}

impl GraphBuilder {
    /// ChiselTrace-compatible constructor (clock `clock`, reset `reset`).
    pub fn new(vcd_path: impl AsRef<Path>, extra_scopes: Vec<String>, pdg: PDGSpec) -> Result<GraphBuilder> {
        Self::with_signals(vcd_path, TraceSignals::chiseltrace(extra_scopes), pdg)
    }

    pub fn with_signals(vcd_path: impl AsRef<Path>, signals: TraceSignals, pdg: PDGSpec) -> Result<GraphBuilder> {
        let vcd_reader = VcdReader::new(vcd_path, &signals)?;

        // Link up the nodes for easier processing
        let linked = pdg.vertices.iter().map(|v| {
            Rc::new(RefCell::new(PDGNode {inner: Rc::new(v.clone()), provides: vec![], dependencies: vec![] }))
        }).collect::<Vec<_>>();

        // Compute adjecency lists (kind of) to reduce time complexity
        let mut edges_by_from: HashMap<u32, Vec<_>> = HashMap::new();
        let mut edges_by_to: HashMap<u32, Vec<_>> = HashMap::new();
        for edge in &pdg.edges {
            edges_by_from.entry(edge.from).or_default().push(edge);
            edges_by_to.entry(edge.to).or_default().push(edge);
        }

        for (node_idx, node) in linked.iter().enumerate() {
            for edge in edges_by_from.get(&(node_idx as u32)).into_iter().flatten() {
                let mut node_ref = node.borrow_mut();
                node_ref.dependencies.push((linked[edge.to as usize].clone(), (*edge).clone()));
            }
            for edge in edges_by_to.get(&(node_idx as u32)).into_iter().flatten() {
                node.borrow_mut().provides.push((linked[edge.from as usize].clone(), (*edge).clone()));
            }
        }

        let mut builder = GraphBuilder { accuracy: crate::pdg_spec::TraceAccuracy::from_spec(&pdg), reader: vcd_reader, pdg, linked_nodes: linked, dependency_state: HashMap::new(), signals };
        builder.init_watches();
        Ok(builder)
    }

    /// SPINALTRACE: watch predicates, every probe named in a vertex/edge condition and switch-key
    /// signals. ChiselTrace only watched VCD variables whose name starts with `probe_`.
    fn init_watches(&mut self) {
        let mut names: Vec<String> = self.pdg.predicates.iter().map(|p| p.name.clone()).collect();
        for v in &self.pdg.vertices {
            if let Some(c) = &v.condition { names.extend(c.probe_name.iter().cloned()); }
        }
        for e in &self.pdg.edges {
            if let Some(c) = &e.condition { names.extend(c.probe_name.iter().cloned()); }
        }
        fn keys(nodes: &[CFGSpecStatement], out: &mut Vec<String>) {
            for n in nodes {
                for b in [&n.true_branch, &n.false_branch, &n.default_branch].into_iter().flatten() { keys(b, out); }
                for c in n.cases.iter().flatten() {
                    out.extend(c.keys.iter().filter_map(|k| k.signal.clone()));
                    keys(&c.branch, out);
                }
            }
        }
        keys(&self.pdg.cfg, &mut names);
        let mut seen = HashSet::new();
        for name in names {
            if !seen.insert(name.clone()) { continue; }
            match self.reader.find_var(&name) {
                Ok(id) => self.reader.watched.entry(id).or_default().push(name),
                Err(_) => {
                    self.accuracy.report("incomplete", format!("Missing predicate/probe: {}", name));
                    eprintln!("warning: signal '{}' (predicate/probe) not found under scope '{}' in the VCD; \
                    conditions on it are never satisfied", name, self.reader.extra_scopes.join(" "));
                },
            }
        }
    }

    pub fn process(&mut self, criterion: &CriterionType, max_timesteps: Option<i64>, processing_type: GraphProcessingType) -> Result<Rc<RefCell<DynPDGNode>>> {
        let mut eof_reached = false;
        let mut criterion_node = None;
        let mut cycle: i64 = 0;

        let mut delayed_statement_buffer: Vec<(i64, u32)> = vec![];

        let mut dependency_state_snapshots: HashMap<i64, (HashMap<String, ProviderSet>, HashMap<String, String>, HashMap<Rc<PDGSpecNode>, DynRef>)> = HashMap::new();
        // SPINALTRACE: keep snapshots for the longest delay in the design.
        let max_assign_delay = self.pdg.vertices.iter().map(|v| v.assign_delay as i64).max().unwrap_or(0);

        while !eof_reached && cycle * 2 <= max_timesteps.unwrap_or(i64::MAX) {
            eof_reached = self.reader.read_cycle_changes()?;
            if self.reader.values.values().any(|v| v.chars().any(|b| b != '0' && b != '1')) {
                self.accuracy.report("incomplete", "A sampled predicate/probe has an unknown VCD value.");
            }
            let corrected_timestamp = cycle; // Time starts at zero
            // SPINALTRACE: stop in the requested cycle; its register updates (taking effect after the
            // edge that ends it) are not applied, so a signal criterion reports the value *during* it.
            let stop_here = match self.signals.stop_at {
                StopAt::End => false,
                StopAt::Cycle(n) => corrected_timestamp >= n,
                StopAt::Time(t) => self.reader.last_edge_time.map_or(true, |e| e > t),
            };
            let activated_statements = self.get_activated_statements();
            let mut new_reg_providers: Vec<(String, Option<String>, DynRef)> = vec![];
            let mut controlflow_providers: HashMap<Rc<PDGSpecNode>, Rc<RefCell<DynPDGNode>>> = HashMap::new();
            let mut new_nodes = vec![];
            let mut reset_dominated: HashSet<String> = HashSet::new();

            // Get the ready delayed statements
            let mut ready_statements = vec![];
            delayed_statement_buffer = delayed_statement_buffer.into_iter().filter(|(t, stmt)| {
                if *t == corrected_timestamp {
                    ready_statements.push(*stmt);
                    false
                } else { true }
            }).collect::<Vec<_>>();
            let ready_set: HashSet<u32> = ready_statements.iter().cloned().collect();

            // Determine the delayed statements -> sequential memory
            let (mut activated_statements, delayed_statements): (Vec<_>, Vec<_>) = activated_statements.into_iter().partition(|stmt| {
                let node = self.linked_nodes[*stmt as usize].borrow();
                node.inner.assign_delay == 0
            });

            let mut delayed_statements_present = false;
            for del_stmt in delayed_statements {
                let node = self.linked_nodes[del_stmt as usize].borrow();
                // SPINALTRACE: a delayed (sync read) statement's own condition (e.g. read enable) is
                // evaluated when the read is issued, not when its data appears.
                if !condition_satisfied(&node.inner.condition, &self.reader.values) {
                    continue;
                }
                delayed_statement_buffer.push((corrected_timestamp + node.inner.assign_delay as i64, del_stmt));
                delayed_statements_present = true;
            }

            activated_statements.append(&mut ready_statements);

            // SPINALTRACE: reset sampling. ChiselTrace looked at the last reset value read (which can be a
            // post-edge change) and let same-cycle register writes override the reset value.
            let reset_kind = if self.reader.reset.is_some() { self.signals.reset_kind } else { ResetKind::None };
            let reset_at_edge = self.reader.reset_active();
            let reset_seen = self.reader.reset_seen;

            for stmt in &activated_statements {
                let node = self.linked_nodes[*stmt as usize].borrow();
                // Without this fix, we get a situation where registers of timestamp x can depend on wires from timestamp x, which is clearly
                // incorrect if you operate under the assumption that on each rising edge, the registers update, THEN the wires that depend on those
                // update
                let node_timestamp = if node.inner.clocked { corrected_timestamp } else { corrected_timestamp.saturating_sub(1) };
                let dpdg_node = Rc::new(RefCell::new(DynPDGNode {inner: node.inner.clone(), timestamp: node_timestamp, dependencies: vec![]}));
                new_nodes.push((self.linked_nodes[*stmt as usize].clone(), dpdg_node.clone()));

                let conditions_satisfied = ready_set.contains(stmt) || condition_satisfied(&node.inner.condition, &self.reader.values);
                // First, update all the wires dependencies. This will determine during the dependency finding which statement will provide which
                // wire value (this is possible because we are just tracing dependencies between statements). In the same pass, we can do registers.
                // We will have to place them in a buffer, because the dependencies are delayed by one clock cycle.
                if conditions_satisfied {
                    if let Some(symb) = &node.inner.assigns_to { // Add conditions
                        let range = node.inner.assign_range.as_ref();
                        if node.inner.clocked {
                            if node.inner.kind == PDGSpecNodeKind::DataDefinition {
                                // Handle register resets (init values).
                                let immediate = corrected_timestamp == 0 || (reset_kind == ResetKind::Async && reset_seen);
                                let at_edge = reset_at_edge && reset_kind != ResetKind::None;
                                if immediate {
                                    dpdg_node.borrow_mut().timestamp -= 1;
                                    self.dependency_state.entry(symb.clone()).or_default().assign(range, dpdg_node.clone());
                                }
                                if at_edge {
                                    // Reset held over the edge: the register stays at its init value.
                                    reset_dominated.insert(symb.clone());
                                    let init_node = if immediate { dpdg_node.clone() } else {
                                        let n = Rc::new(RefCell::new(DynPDGNode {inner: node.inner.clone(), timestamp: corrected_timestamp, dependencies: vec![]}));
                                        new_nodes.push((self.linked_nodes[*stmt as usize].clone(), n.clone()));
                                        n
                                    };
                                    new_reg_providers.push((symb.clone(), range.cloned(), init_node));
                                }
                            } else {
                                new_reg_providers.push((symb.clone(), range.cloned(), dpdg_node.clone()));
                            }
                        } else {
                            self.dependency_state.entry(symb.clone()).or_default().assign(range, dpdg_node.clone());
                        }
                    }

                    if node.inner.kind == PDGSpecNodeKind::ControlFlow {
                        controlflow_providers.insert(node.inner.clone(), dpdg_node.clone());
                    }
                }
            }
            if !reset_dominated.is_empty() {
                new_reg_providers.retain(|(s, _, n)| !reset_dominated.contains(s) || n.borrow().inner.kind == PDGSpecNodeKind::DataDefinition);
            }
            for (node, dpdg_node) in &new_nodes {
                // Account for delayed assignments
                let node_delay = node.borrow().inner.assign_delay;
                let (dep_state, probe_vals, cf_providers) = match dependency_state_snapshots.get(&(corrected_timestamp - node_delay as i64)) {
                    Some(x) if node_delay > 0 => (&x.0, &x.1, &x.2),
                    _ => (&self.dependency_state, &self.reader.values, &controlflow_providers),
                };
                // A statement may depend on multiple statements that provide the same symbol.
                // We only want to process the symbol once, otherwise we get duplicate dependencies.
                let mut deps_processed = HashSet::new();
                for (dep_node, dep_edge) in &node.borrow().dependencies {
                    if let Some(ref assigns_to) = dep_node.borrow().inner.assigns_to {
                        if deps_processed.contains(&(assigns_to.clone(), dep_edge.kind)) {
                            continue;
                        }
                    }

                    if processing_type == GraphProcessingType::DataOnly && dep_edge.kind != PDGSpecEdgeKind::Data {
                        continue;
                    }

                    if condition_satisfied(&dep_edge.condition, probe_vals) {
                        match dep_edge.kind {
                            PDGSpecEdgeKind::Declaration => {
                                // Only add if the graph processing type is "Full", because this is only required for slicing, not ChiselTrace itself
                                if processing_type == GraphProcessingType::Full {
                                    // Just create a new one. I know this is a bit of an afterthought, but this is a simple way to make
                                    // the dynamic slicing work. It doesn't need further processing anyway, so we can create as many nodes
                                    // as we want.
                                    let dep = Rc::new(RefCell::new(DynPDGNode {inner: dep_node.borrow().inner.clone(), timestamp: corrected_timestamp - 1, dependencies: vec![]}));
                                    dpdg_node.borrow_mut().dependencies.push((dep.clone(), dep_edge.kind));
                                }
                            }
                            PDGSpecEdgeKind::Data | PDGSpecEdgeKind::Index  => {
                                // Data dependencies should not be resolved using snapshotted dependencies.
                                let dep_state = if dep_edge.kind == PDGSpecEdgeKind::Data {
                                    &self.dependency_state
                                } else {
                                    dep_state
                                };
                                if let Some(dep_str) = &dep_node.borrow().inner.assigns_to {
                                    if let Some(providers) = dep_state.get(dep_str) {
                                        for dep in providers.all() {
                                            // Never depend on yourself within the same activation.
                                            if !Rc::ptr_eq(dep, dpdg_node) {
                                                dpdg_node.borrow_mut().dependencies.push((dep.clone(), dep_edge.kind));
                                            }
                                        }
                                    }
                                    // SPINALTRACE: dedupe per (symbol, kind): a signal can be both a data
                                    // input and an index of the same statement.
                                    deps_processed.insert((dep_str.clone(), dep_edge.kind));
                                }
                            }
                            PDGSpecEdgeKind::Conditional => {
                                // SPINALTRACE: delayed statements use the control flow of their issue cycle.
                                if let Some(cond_dep) = cf_providers.get(&dep_node.borrow().inner) {
                                    dpdg_node.borrow_mut().dependencies.push((cond_dep.clone(), PDGSpecEdgeKind::Conditional));
                                }
                            }
                        }
                    }
                }
            }

            // If there are delayed statements, we need to save a snapshot of the dependencies, because
            // control flow and index flow need to be of the current timestamp, while the data flow is actually not (for SRAM at least).
            if delayed_statements_present {
                dependency_state_snapshots.insert(corrected_timestamp, (self.dependency_state.clone(), self.reader.values.clone(), controlflow_providers.clone()));
            }
            // SPINALTRACE: drop snapshots nobody can use any more.
            dependency_state_snapshots.retain(|t, _| *t >= corrected_timestamp - max_assign_delay);

            for (_,n) in new_nodes {
                 if match criterion {
                    CriterionType::Statement(c) => n.borrow().inner.name.eq(c),
                    CriterionType::Signal(_) => false,
                    CriterionType::Line(f, l) => n.borrow().inner.line == *l && n.borrow().inner.file.ends_with(f.as_str()),
                } {
                    criterion_node = Some(n)
                }
            }
            if stop_here {
                break;
            }
            for (k, range, v) in new_reg_providers {
                self.dependency_state.entry(k).or_default().assign(range.as_ref(), v);
            }
            cycle += 1;
        }

        let exported_node = match criterion {
            CriterionType::Statement(_) | CriterionType::Line(_, _) => criterion_node.as_ref(),
            // If we are looking for a signal, give the latest assignment.
            CriterionType::Signal(c) => self.dependency_state.get(c).and_then(|p| p.latest())
        }.ok_or(Error::StatementLookupError("Criterion not found in DPDG".into()))?;

        Ok(exported_node.clone())
    }

    fn get_activated_statements(&mut self) -> Vec<u32> {
        let mut activated = Vec::new();

        let mut stack = self.pdg.cfg.clone();
        stack.reverse();

        let values = &self.reader.values;
        while let Some(node) = stack.pop() {
            activated.push(node.stmt_ref);
            if let Some(pred) = node.pred_stmt_ref {
                let pred_name = &self.pdg.predicates[pred as usize].name;
                let pred_value = values.get(pred_name).map(|s| s.as_str()).unwrap_or("x");
                if let Some(cases) = node.cases {
                    // SPINALTRACE: switch fork, first matching case wins (Spinal `switch` semantics).
                    let taken = cases.into_iter().find(|c| c.keys.iter().any(|k| key_matches(k, pred_value, values)));
                    match taken {
                        Some(c) => stack.extend(c.branch.into_iter().rev()),
                        None => if let Some(d) = node.default_branch { stack.extend(d.into_iter().rev()) }
                    }
                } else if is_truthy(pred_value) {
                    if let Some(t_branch) = node.true_branch {
                        stack.extend(t_branch.into_iter().rev());
                    }
                } else if let Some(f_branch) = node.false_branch {
                    stack.extend(f_branch.into_iter().rev());
                }
            }
        }

        activated
    }
}

fn value_bits(v: &vcd::Value) -> char {
    match v {
        vcd::Value::V0 => '0',
        vcd::Value::V1 => '1',
        vcd::Value::X => 'x',
        vcd::Value::Z => 'z',
    }
}

fn vector_bits(v: &vcd::Vector) -> String {
    v.iter().map(|b| value_bits(&b)).collect()
}

impl VcdReader {
    fn new(vcd_path: impl AsRef<Path>, signals: &TraceSignals) -> Result<Self> {
        let mut parser = crate::vcd_input::open(vcd_path)?;
        let header = parser.parse_header()?;
        let extra_scopes = signals.extra_scopes.clone();

        let mut clock_path = extra_scopes.clone();
        clock_path.extend(signals.clock.split('.').map(String::from));
        let clock = header.find_var(&clock_path).ok_or_else(|| {
            anyhow::anyhow!(Error::ClockNotFoundError).context(format!(
                "clock '{}' not found in the VCD (looked for '{}'); check --clock / --extra-scopes",
                signals.clock, clock_path.join(" ")))
        })?.code;

        let reset = match &signals.reset {
            Some(r) => {
                let mut reset_path = extra_scopes.clone();
                reset_path.extend(r.split('.').map(String::from));
                let found = header.find_var(&reset_path).map(|v| v.code);
                if found.is_none() {
                    anyhow::bail!("reset '{}' not found in the VCD ({}); use --no-reset only for a design without reset",
                        r, reset_path.join(" "));
                }
                found
            }
            None => None,
        };

        Ok(VcdReader { parser, extra_scopes, header, clock, reset,
            reset_active_value: if signals.reset_active_low { '0' } else { '1' },
            clock_val: vcd::Value::X, watched: HashMap::new(), values: HashMap::new(), pending: vec![],
            reset_value: 'x', reset_seen: false, last_edge_time: None, block_time: 0 })
    }

    fn find_var(&self, hierarchy: impl AsRef<str>) -> Result<IdCode> {
        let mut hier_path = self.extra_scopes.iter().map(|s| s.as_str()).collect::<Vec<_>>();
        hier_path.extend(hierarchy.as_ref().split("."));
        Ok(self.header.find_var(&hier_path).ok_or(Error::VariableNotFoundError(hier_path.join(".")))?.code)
    }

    fn reset_active(&self) -> bool {
        self.reset.is_some() && self.reset_value == self.reset_active_value
    }

    fn commit(&mut self, first_of_cycle: bool) {
        for (id, bits) in self.pending.drain(..) {
            if Some(id) == self.reset {
                self.reset_value = bits.chars().last().unwrap_or('x');
            }
            if let Some(names) = self.watched.get(&id) {
                for n in names {
                    self.values.insert(n.clone(), bits.clone());
                }
            }
        }
        // The first commit of a cycle holds the changes made right after its opening edge (e.g. a reset
        // released at that edge): only the resulting value counts, not the one before it.
        if first_of_cycle {
            self.reset_seen = self.reset_active();
        } else if self.reset_active() {
            self.reset_seen = true;
        }
    }

    /// Reads one clock cycle: everything up to (and excluding) the changes recorded at the next rising
    /// edge, which take place *after* the edge and belong to the next cycle. Returns true at EOF.
    fn read_cycle_changes(&mut self) -> Result<bool> {
        let mut rising_edge_found = false;
        let mut eof_reached = true;
        let mut first_commit = true;
        self.reset_seen = self.reset_active();
        while let Some(command) = self.parser.next() {
            let command = command?;
            match command {
                Command::Timestamp(t) => {
                    // The events that are recorded at the same step as a rising edge take place *after* the clock edge.
                    // Therefore, they should be processed at the next time step.
                    if rising_edge_found {
                        self.last_edge_time = Some(self.block_time);
                        self.block_time = t;
                        eof_reached = false;
                        break;
                    } else {
                        self.commit(first_commit);
                        first_commit = false;
                    }
                    self.block_time = t;
                }
                Command::ChangeScalar(i, v) => {
                    if i == self.clock {
                        if self.clock_val == vcd::Value::V0 && v == vcd::Value::V1 {
                            rising_edge_found = true;
                        }
                        self.clock_val = v;
                    }
                    if self.watched.contains_key(&i) || Some(i) == self.reset {
                        self.pending.push((i, value_bits(&v).to_string()));
                    }
                }
                Command::ChangeVector(i, v) => {
                    if i == self.clock {
                        let nv = v.iter().last().unwrap_or(vcd::Value::X);
                        if self.clock_val == vcd::Value::V0 && nv == vcd::Value::V1 {
                            rising_edge_found = true;
                        }
                        self.clock_val = nv;
                    }
                    if self.watched.contains_key(&i) || Some(i) == self.reset {
                        self.pending.push((i, vector_bits(&v)));
                    }
                }
                _ => ()
            }
        }
        if eof_reached {
            if rising_edge_found {
                self.last_edge_time = Some(self.block_time);
            } else {
                // SPINALTRACE: the tail after the last edge is a (final) cycle of its own.
                self.commit(first_commit);
                self.last_edge_time = None;
            }
        }

        Ok(eof_reached)
    }
}

/// SPINALTRACE: number of the cycle that contains VCD time `t` (cycle n ends at the n-th rising edge).
pub fn cycle_at_time(vcd_path: impl AsRef<Path>, extra_scopes: &[String], clock: &str, t: u64) -> Result<i64> {
    let mut parser = crate::vcd_input::open(vcd_path)?;
    let header = parser.parse_header()?;
    let mut path = extra_scopes.to_vec();
    path.extend(clock.split('.').map(String::from));
    let clk = header.find_var(&path).ok_or(Error::ClockNotFoundError)?.code;
    let mut now = 0u64;
    let mut last = vcd::Value::X;
    let mut edges = 0i64;
    for c in parser {
        match c? {
            Command::Timestamp(ts) => { now = ts; if now > t { break; } }
            Command::ChangeScalar(i, v) if i == clk => {
                if last == vcd::Value::V0 && v == vcd::Value::V1 && now <= t { edges += 1; }
                last = v;
            }
            _ => ()
        }
    }
    Ok(edges)
}

#[cfg(test)]
mod tests {
    use super::*;

    fn node(name: &str) -> DynRef {
        Rc::new(RefCell::new(DynPDGNode { inner: Rc::new(PDGSpecNode { file: String::new(), line: 0, char: 0, name: name.into(),
            kind: PDGSpecNodeKind::Connection, clocked: false, module_path: vec![], related_signal: None, assigns_to: None,
            is_chisel_statement: true, condition: None, assign_delay: 0, assign_range: None }), timestamp: 0, dependencies: vec![] }))
    }

    #[test]
    fn bits() {
        assert_eq!(bits_to_u64("0101"), Some(5));
        assert_eq!(bits_to_u64("x1"), None);
        assert!(is_truthy("1") && !is_truthy("0") && !is_truthy("x"));
        assert_eq!(pad_to("101", 5), "00101");
        assert_eq!(pad_to("x1", 4), "xxx1");
    }

    #[test]
    fn case_keys() {
        let values = HashMap::from([("k".to_string(), "10".to_string())]);
        let pat = |p: &str| CFGCaseKey { pattern: Some(p.into()), signal: None };
        assert!(key_matches(&pat("0101"), "101", &values));
        assert!(key_matches(&pat("01-1"), "0111", &values));
        assert!(!key_matches(&pat("01-1"), "0110", &values));
        assert!(!key_matches(&pat("0001"), "000x", &values));
        let sig = CFGCaseKey { pattern: None, signal: Some("k".into()) };
        assert!(key_matches(&sig, "010", &values));
        assert!(!key_matches(&sig, "011", &values));
    }

    #[test]
    fn provider_sets() {
        let mut p = ProviderSet::default();
        p.assign(None, node("full"));
        p.assign(Some(&"3".to_string()), node("bit3"));
        p.assign(Some(&"3".to_string()), node("bit3b"));
        p.assign(Some(&"7:4".to_string()), node("hi"));
        let names: Vec<String> = p.all().map(|n| n.borrow().inner.name.clone()).collect();
        assert_eq!(names, vec!["full", "bit3b", "hi"]);
        assert_eq!(p.latest().unwrap().borrow().inner.name, "hi");
        p.assign(None, node("full2"));
        assert_eq!(p.all().count(), 1);
        for _ in 0..40 { p.assign(Some(&"dyn".to_string()), node("d")); }
        assert_eq!(p.all().count(), 1 + MAX_DYN_PARTIALS);
    }
}
