// SpinalTrace CLI. Forked from chiseltrace-cli (jarlb/chiseltrace f4bf63a, Apache-2.0).
// SPINALTRACE: positional `dyn-pdg` arguments replaced by flags shared with the GUI; signal names,
// scopes, reset handling and the stop time are configurable; HGLDD is optional.
use std::{fs::{read_to_string, File}, io::BufWriter, path::PathBuf};
use anyhow::Result;
use clap::{Args as ClapArgs, Parser, Subcommand};
use spinaltrace_rs::{conversion::pdg_convert_to_source, graphbuilder::{GraphBuilder, GraphProcessingType, ResetKind, StopAt}, pipeline::{self, parse_reset_kind, TraceRequest}, slicing::{pdg_slice, write_dynamic_slice, write_static_slice}, util::parse_criterion};
use spinaltrace_rs::graphbuilder::CriterionType;
use spinaltrace_rs::pdg_spec::PDGSpec;
use serde::Deserialize;

#[derive(Parser, Debug)]
#[command(name = "spinaltrace-cli", version, about = "SpinalTrace: dynamic signal-dependency tracing for SpinalHDL (CLI)", long_about = None)]
struct Args {
    #[command(subcommand)]
    command: Commands,
}

/// Options shared by the dynamic commands (and by the GUI).
#[derive(ClapArgs, Debug, Clone)]
struct TraceArgs {
    /// Criterion: 'signal:<path>' (RTL path like io_result or Spinal path like io.result),
    /// 'statement:<name>' (e.g. statement:connect_io_result) or 'line:<file>:<line>'
    #[arg(short, long, value_parser = parse_criterion)]
    slice_criterion: CriterionType,
    /// Path to the program dependency graph (W/spinaltrace/pdg.json)
    #[arg(short, long)]
    pdg_path: PathBuf,
    /// Path to the VCD file
    #[arg(short, long)]
    vcd_path: PathBuf,
    /// HGLDD directory (SpinalWaves); optional, without it raw VCD values are shown
    #[arg(long)]
    hgldd_path: Option<PathBuf>,
    /// The name of the top-level module (default: from the PDG)
    #[arg(short, long)]
    top_module: Option<String>,
    /// VCD scopes above the toplevel's signals (default: from the PDG, e.g. "TOP GCD")
    #[arg(short, long, value_delimiter = ' ', num_args = 1..)]
    extra_scopes: Option<Vec<String>>,
    /// Clock signal below the extra scopes (default: from the PDG, Spinal "clk")
    #[arg(long)]
    clock: Option<String>,
    /// Reset signal below the extra scopes (default: from the PDG, Spinal "reset")
    #[arg(long)]
    reset: Option<String>,
    /// Ignore the reset signal (init values apply at t=0 only)
    #[arg(long, default_value_t = false)]
    no_reset: bool,
    /// Reset is active low (default: from the PDG)
    #[arg(long, num_args = 0..=1, default_missing_value = "true")]
    reset_active_low: Option<bool>,
    /// Reset kind: async, sync or none (default: from the PDG)
    #[arg(long, value_parser = parse_reset_kind)]
    reset_kind: Option<ResetKind>,
    /// ChiselTrace compatibility: analyse cycles 0..=N/2
    #[arg(long)]
    max_timesteps: Option<u64>,
    /// Stop in cycle N (0 = before the first rising edge); a signal criterion reports its value during that cycle
    #[arg(long, conflicts_with = "at_time")]
    at_cycle: Option<i64>,
    /// Stop in the cycle containing this VCD time (e.g. the time of a failed check)
    #[arg(long)]
    at_time: Option<u64>,
    /// Only trace data dependencies
    #[arg(long, num_args = 0..=1, default_missing_value = "true")]
    data_only: Option<bool>,
    /// Keep the netlist-level graph (no grouping into source statements)
    #[arg(long, num_args = 0..=1, default_missing_value = "true")]
    fir: Option<bool>,
}

impl TraceArgs {
    fn request(&self, processing: GraphProcessingType) -> TraceRequest {
        let mut r = TraceRequest::new(self.pdg_path.clone(), self.vcd_path.clone(), self.slice_criterion.clone());
        r.hgldd_path = self.hgldd_path.clone();
        r.top_module = self.top_module.clone();
        r.extra_scopes = self.extra_scopes.clone();
        r.clock = self.clock.clone();
        r.reset = self.reset.clone();
        r.no_reset = self.no_reset;
        r.reset_active_low = self.reset_active_low;
        r.reset_kind = self.reset_kind;
        r.max_timesteps = self.max_timesteps.map(|x| x as i64);
        r.stop_at = match (self.at_cycle, self.at_time) {
            (Some(c), _) => StopAt::Cycle(c),
            (_, Some(t)) => StopAt::Time(t),
            _ => StopAt::End,
        };
        r.processing_type = if self.data_only.unwrap_or(false) { GraphProcessingType::DataOnly } else { processing };
        r.convert_to_source = !self.fir.unwrap_or(false);
        r
    }
}

#[derive(Subcommand, Debug)]
enum Commands {
    /// Perform a static slice operation.
    Slice {
        /// The path to the input PDG
        path: String,
        /// The statement that should be used for the program slicing.
        slice_criterion: String,

        #[clap(default_value = "slice.json")]
        output_path: String,
    },
    /// Build the dynamic program dependency graph of a criterion (what the GUI shows).
    #[command(name = "dyn-pdg", alias = "dynpdg", alias = "dyn-p-d-g")]
    DynPDG {
        #[command(flatten)]
        trace: TraceArgs,
        /// Output JSON (ExportablePDG)
        #[arg(short, long, default_value = "dynpdg.json")]
        output_path: PathBuf,
        /// Print a human-readable summary of the traced statements
        #[arg(long, default_value_t = false)]
        summary: bool,
    },
    /// Dynamic slice: the source statements that influenced the criterion.
    DynSlice {
        #[command(flatten)]
        trace: TraceArgs,
        #[arg(short, long, default_value = "dynslice.json")]
        output_path: PathBuf,
    },
    /// Convert a netlist-level PDG to the source-statement representation.
    Convert {
        /// The path to the input PDG
        path: String,
        #[clap(default_value = "converted_pdg.json")]
        output_path: String,
    }
}

fn read_spec(path: &str) -> Result<PDGSpec> {
    let buf = read_to_string(path)?;
    let mut deser = serde_json::Deserializer::from_str(buf.as_str());
    deser.disable_recursion_limit();
    Ok(PDGSpec::deserialize(&mut deser)?)
}

fn main() -> Result<()> {
    let args = Args::parse();

    match &args.command {
        Commands::Slice { path, slice_criterion, output_path } => {
            let sliced = pdg_slice(read_spec(path)?, slice_criterion)?;
            let converted = pdg_convert_to_source(sliced.into(), true, false);
            write_static_slice(&converted, output_path)?;
        },
        Commands::Convert { path, output_path } => {
            let converted = pdg_convert_to_source(read_spec(path)?.into(), true, false);
            let output_file = File::create(output_path)?;
            let writer = BufWriter::new(output_file);
            serde_json::to_writer_pretty(writer, &converted)?;
        },
        Commands::DynPDG { trace, output_path, summary } => {
            let req = trace.request(GraphProcessingType::Normal);
            eprintln!("Building dynamic PDG for {:?}", req.criterion);
            let converted_pdg = pipeline::trace(&req)?;
            eprintln!("Num verts: {}, num edges: {}", converted_pdg.vertices.len(), converted_pdg.edges.len());
            let f = File::create(output_path)?;
            let writer = BufWriter::new(f);
            serde_json::to_writer_pretty(writer, &converted_pdg)?;
            if *summary {
                print!("{}", pipeline::summary(&converted_pdg));
            }
        }
        Commands::DynSlice { trace, output_path } => {
            let req = trace.request(GraphProcessingType::Full);
            let pdg = pipeline::read_pdg(&req.pdg_path)?;
            for w in pipeline::design_warnings(&pdg) { eprintln!("warning: {}", w); }
            let (signals, _) = pipeline::resolve_signals(&pdg, &req);
            let criterion = pipeline::resolve_criterion(&pdg, &req.criterion);
            let mut builder = GraphBuilder::with_signals(&req.vcd_path, signals, pdg)?;
            let dpdg = builder.process(&criterion, req.max_timesteps, GraphProcessingType::Full)?;
            write_dynamic_slice(&dpdg, output_path)?;
        }
    }

    Ok(())
}
