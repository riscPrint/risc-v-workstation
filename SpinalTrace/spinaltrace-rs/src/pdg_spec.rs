use std::{cell::RefCell, rc::Rc};

use serde::{Serialize, Deserialize};

#[derive(Serialize, Deserialize, Debug)]
pub struct PDGSpec {
    pub vertices: Vec<PDGSpecNode>,
    pub edges: Vec<PDGSpecEdge>,
    pub predicates: Vec<PDGSpecNode>,
    pub cfg: Vec<CFGSpecStatement>,
    /// SpinalTrace extension: design metadata written by the Spinal front-end (absent in ChiselTrace PDGs).
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub spinaltrace: Option<SpinalTraceMeta>
}

impl PDGSpec {
    pub fn _empty() -> Self {
        PDGSpec { vertices: vec![], edges: vec![], predicates: vec![], cfg: vec![], spinaltrace: None }
    }
}

/// SpinalTrace extension: metadata about the traced design (see docs/PDG_FORMAT.md).
#[derive(Serialize, Deserialize, Debug, Clone, Default)]
#[serde(rename_all = "camelCase")]
pub struct SpinalTraceMeta {
    #[serde(default)]
    pub format_version: u32,
    #[serde(default)]
    pub toplevel: String,
    /// VCD scopes above the toplevel's signals (e.g. `TOP GCD` for Verilator).
    #[serde(default)]
    pub extra_scopes: Vec<String>,
    #[serde(default)]
    pub clock_domains: Vec<ClockDomainMeta>,
    #[serde(default)]
    pub warnings: Vec<String>
}

#[derive(Serialize, Deserialize, Debug, Clone, Default)]
#[serde(rename_all = "camelCase")]
pub struct ClockDomainMeta {
    pub clock: String,
    #[serde(default)]
    pub reset: Option<String>,
    /// "ASYNC", "SYNC" or "BOOT" (Spinal ResetKind)
    #[serde(default)]
    pub reset_kind: String,
    #[serde(default)]
    pub reset_active_low: bool,
    #[serde(default)]
    pub clock_enable: Option<String>,
    #[serde(default)]
    pub soft_reset: Option<String>,
    #[serde(default)]
    pub registers: u32
}

#[derive(Serialize, Deserialize, Debug, Clone, Hash, PartialEq, Eq)]
#[serde(rename_all = "camelCase")]
pub struct PDGSpecNode {
    pub file: String,
    pub line: u32,
    pub char: u32,
    pub name: String,
    pub kind: PDGSpecNodeKind,
    pub clocked: bool,
    #[serde(default)]
    pub module_path: Vec<String>,
    pub related_signal: Option<PDGSpecRelatedSignal>,
    pub assigns_to: Option<String>,
    pub is_chisel_statement: bool,
    pub condition: Option<PDGSpecCondition>,
    #[serde(default)]
    pub assign_delay: u32,
    /// SpinalTrace extension: key of a partial (bit / range) assignment. `None` = full assignment,
    /// which replaces every earlier provider of the signal; a partial assignment only replaces the
    /// provider with the same key ("dyn" = dynamic index, never replaces).
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub assign_range: Option<String>
}

#[derive(Serialize, Deserialize, Debug, Clone, Copy, PartialEq, Hash, Eq)]
pub enum PDGSpecNodeKind {
    Definition,
    DataDefinition,
    IO,
    Connection,
    ControlFlow,
}

#[derive(Serialize, Deserialize, Debug, Clone, Hash, PartialEq, Eq)]
#[serde(rename_all = "camelCase")]
pub struct PDGSpecRelatedSignal {
    pub signal_path: String,
    pub field_path: String
}

#[derive(Serialize, Deserialize, Debug, Clone, PartialEq, Eq, Hash)]
pub struct PDGSpecEdge {
    pub from: u32,
    pub to: u32,
    pub kind: PDGSpecEdgeKind,
    pub clocked: bool,
    pub condition: Option<PDGSpecCondition>
}

#[derive(Serialize, Deserialize, Debug, Clone, Copy, PartialEq, Eq, Hash)]
pub enum PDGSpecEdgeKind {
    Data,
    Conditional,
    Declaration,
    Index
}

#[derive(Serialize, Deserialize, Debug, Clone, Hash, PartialEq, Eq)]
#[serde(rename_all = "camelCase")]
pub struct PDGSpecCondition {
    pub probe_name: Vec<String>,
    pub probe_value: Vec<u64>
}

// Warning: do not debug print this using the standard trait implementation, it is a linked structure and it will result in infinite recursion
pub struct LinkedPDGNode {
    pub _file: String,
    pub _line: u32,
    pub name: String,
    pub _kind: PDGSpecNodeKind,
    pub connections: Vec<Rc<RefCell<LinkedPDGNode>>>,
    pub visited: bool
}

impl From<&PDGSpecNode> for LinkedPDGNode {
    fn from(value: &PDGSpecNode) -> Self {
        LinkedPDGNode { _file: value.file.clone(), _line: value.line, name: value.name.clone(), _kind: value.kind, connections: Vec::new(), visited: false }
    }
}

#[derive(Debug, Deserialize, Serialize, Clone)]
#[serde(rename_all = "camelCase")]
pub struct CFGSpecStatement {
    pub stmt_ref: u32,
    #[serde(default)]
    pub pred_stmt_ref: Option<u32>,
    #[serde(default)]
    pub true_branch: Option<Vec<CFGSpecStatement>>,
    #[serde(default)]
    pub false_branch: Option<Vec<CFGSpecStatement>>,
    /// SpinalTrace extension: a `switch` fork. The predicate holds the switch value; the first case
    /// with a matching key is taken, otherwise `default_branch`.
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub cases: Option<Vec<CFGSpecCase>>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub default_branch: Option<Vec<CFGSpecStatement>>,
}

/// SpinalTrace extension: one `is(...)` of a switch.
#[derive(Debug, Deserialize, Serialize, Clone)]
#[serde(rename_all = "camelCase")]
pub struct CFGSpecCase {
    pub keys: Vec<CFGCaseKey>,
    #[serde(default)]
    pub branch: Vec<CFGSpecStatement>,
}

/// A case key: either a bit pattern (MSB first, '-' = don't care) or the value of another signal.
#[derive(Debug, Deserialize, Serialize, Clone)]
#[serde(rename_all = "camelCase")]
pub struct CFGCaseKey {
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub pattern: Option<String>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub signal: Option<String>,
}

/// A format of the PDG that allows for storage and export of additional information.
#[derive(Debug, Serialize, Deserialize, Clone)]
pub struct ExportablePDG {
    pub vertices: Vec<ExportablePDGNode>,
    pub edges: Vec<ExportablePDGEdge>
}

impl ExportablePDG {
    pub fn empty() -> Self {
        ExportablePDG { vertices: vec![], edges: vec![] }
    }
}

impl From<PDGSpec> for ExportablePDG {
    fn from(value: PDGSpec) -> Self {
        ExportablePDG { vertices: value.vertices.into_iter().map(|v| v.into()).collect(),
            edges: value.edges.into_iter().map(|e| e.into()).collect() }
    }
}

#[derive(Debug, Serialize, Deserialize, Clone)]
pub struct ExportableSlice {
    pub statements: Vec<ExportableSliceStatement>
}

#[derive(Debug, Serialize, Deserialize, Clone, PartialEq, Eq, Hash)]
pub struct ExportableSliceStatement {
    pub file: String,
    pub line: u32,
    pub char: u32
}

impl From<ExportablePDGNode> for ExportableSliceStatement {
    fn from(value: ExportablePDGNode) -> Self {
        ExportableSliceStatement { file: value.file, line: value.line, char: value.char }
    }
}

impl From<PDGSpecNode> for ExportableSliceStatement {
    fn from(value: PDGSpecNode) -> Self {
        ExportableSliceStatement { file: value.file, line: value.line, char: value.char }
    }
}

impl From<Rc<PDGSpecNode>> for ExportableSliceStatement {
    fn from(value: Rc<PDGSpecNode>) -> Self {
        ExportableSliceStatement { file: value.file.clone(), line: value.line, char: value.char }
    }
}

#[derive(Debug, Serialize, Deserialize, Clone, Hash, PartialEq, Eq)]
pub struct ExportablePDGNode {
    pub file: String,
    pub line: u32,
    pub char: u32,
    pub name: String,
    pub kind: PDGSpecNodeKind,
    pub clocked: bool,
    pub module_path: Vec<String>,
    pub related_signal: Option<PDGSpecRelatedSignal>,
    pub sim_data: Option<String>,
    pub timestamp: i64,
    pub is_chisel_assignment: bool,
    /// SpinalTrace extension: RTL path of the assigned signal (used for raw VCD values without HGLDD).
    #[serde(default)]
    pub assigns_to: Option<String>
}

impl From<PDGSpecNode> for ExportablePDGNode {
    fn from(value: PDGSpecNode) -> Self {
        ExportablePDGNode { file: value.file, line: value.line, char: value.char, name: value.name, kind: value.kind,
            clocked: value.clocked, module_path: value.module_path, related_signal: value.related_signal, sim_data: None,
            is_chisel_assignment: value.is_chisel_statement, timestamp: 0, assigns_to: value.assigns_to
        }
    }
}

#[derive(Debug, Serialize, Deserialize, Clone, PartialEq, Eq, Hash)]
pub struct ExportablePDGEdge {
    pub from: u32,
    pub to: u32,
    pub kind: PDGSpecEdgeKind,
    pub clocked: bool
}

impl From<PDGSpecEdge> for ExportablePDGEdge {
    fn from(value: PDGSpecEdge) -> Self {
        ExportablePDGEdge { from: value.from, to: value.to, kind: value.kind, clocked: value.clocked }
    }
}