use std::path::PathBuf;

use clap::Parser;
use anyhow::Result;
use spinaltrace_rs::{
    graphbuilder::{CriterionType, GraphProcessingType, ResetKind, StopAt},
    pipeline::{parse_reset_kind, TraceRequest},
    util::parse_criterion,
};

use crate::errors;

/// A GUI program to visualize Spinal dynamic program dependency graphs
#[derive(Parser, Debug)]
#[command(name = "spinaltrace", version, about, long_about = None)]
pub struct Args {
    /// Criterion: 'signal:<path>' (RTL path like io_result or Spinal path like io.result),
    /// 'statement:<name>' (e.g. statement:connect_io_result) or 'line:<file>:<line>'
    #[arg(short, long, value_parser = parse_criterion)]
    pub slice_criterion: CriterionType,
    /// Path to the program dependency graph (W/spinaltrace/pdg.json)
    #[arg(short, long)]
    pub pdg_path: PathBuf,
    /// Path to the VCD file
    #[arg(short, long)]
    pub vcd_path: PathBuf,
    /// HGLDD directory (SpinalWaves); optional, without it raw VCD values are shown
    #[arg(long)]
    pub hgldd_path: Option<PathBuf>,
    /// The name of the top-level module (default: from the PDG)
    #[arg(short, long)]
    pub top_module: Option<String>,
    /// VCD scopes above the toplevel's signals (default: from the PDG, e.g. "TOP GCD")
    #[arg(short, long, value_delimiter = ' ', num_args = 1..)]
    pub extra_scopes: Option<Vec<String>>,
    /// Clock signal below the extra scopes (default: from the PDG, Spinal "clk")
    #[arg(long)]
    pub clock: Option<String>,
    /// Reset signal below the extra scopes (default: from the PDG, Spinal "reset")
    #[arg(long)]
    pub reset: Option<String>,
    /// Ignore the reset signal (init values apply at t=0 only)
    #[arg(long, default_value_t = false)]
    pub no_reset: bool,
    /// Reset is active low (default: from the PDG)
    #[arg(long, num_args = 0..=1, default_missing_value = "true")]
    pub reset_active_low: Option<bool>,
    /// Reset kind: async, sync or none (default: from the PDG)
    #[arg(long, value_parser = parse_reset_kind)]
    pub reset_kind: Option<ResetKind>,
    /// Legacy compatibility: analyse cycles 0..=N/2
    #[arg(long)]
    pub max_timesteps: Option<u64>,
    /// Stop in cycle N (0 = before the first rising edge); a signal criterion reports its value during that cycle
    #[arg(long, conflicts_with = "at_time")]
    pub at_cycle: Option<i64>,
    /// Stop in the cycle containing this VCD time (e.g. the time of a failed check)
    #[arg(long)]
    pub at_time: Option<u64>,
    /// Only trace data dependencies
    #[arg(long, num_args = 0..=1, default_missing_value = "true")]
    pub data_only: Option<bool>,
    /// Keep the netlist-level graph (no grouping into source statements)
    #[arg(long, num_args = 0..=1, default_missing_value = "true")]
    pub fir: Option<bool>,
    /// Enables hierarchical grouping
    #[arg(long)]
    pub hier_grouping: Option<bool>,
}

impl Args {
    pub fn request(&self, processing: GraphProcessingType) -> TraceRequest {
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

    pub fn validate(self) -> Result<Self> {
        if !self.pdg_path.is_file() {
            anyhow::bail!(errors::Error::ArgumentValidationError("Invalid PDG path".into()));
        }

        if !self.vcd_path.is_file() {
            anyhow::bail!(errors::Error::ArgumentValidationError("Invalid VCD path".into()));
        }

        if let Some(hgldd_path) = &self.hgldd_path {
            if !hgldd_path.is_dir() {
                anyhow::bail!(errors::Error::ArgumentValidationError("Invalid HGLDD path".into()));
            }
        }

        Ok(self)
    }
}
