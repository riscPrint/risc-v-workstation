use std::{collections::{HashMap, HashSet}, sync::{Arc, RwLock, Weak}};

use spinaltrace_rs::{pipeline::TraceRequest, pdg_spec::{ExportablePDG, ExportablePDGNode}};

pub struct AppState {
    pub pdg_config: Option<PDGConfig>,
    pub graph: Option<ViewableGraph>
}

impl AppState {
    pub fn new() -> Self {
        AppState { pdg_config: None, graph: None }
    }
}

#[derive(Debug, Clone)]
pub struct PDGConfig {
    pub request: TraceRequest,
    pub group_nodes: bool,
}

#[derive(Debug, Clone)]
pub struct GraphNodeHierarchy {
    pub instance_name: String,
    pub expanded: bool,
    pub pdg_node: ExportablePDGNode,
    pub node_indices: Vec<usize>,
    pub children: Vec<Arc<RwLock<GraphNodeHierarchy>>>,
    pub parent: Option<Weak<RwLock<GraphNodeHierarchy>>>,
    pub group_id: usize // ID for vis.js
}

/// Datastructure that holds a pruned DPDG (with nodes grouped) and a table of the nodes that are grouped
#[derive(Debug, Clone)]
pub struct HierarchicalGraph {
    pub dpdg: ExportablePDG,
    pub group_ids: HashMap<usize, Arc<RwLock<GraphNodeHierarchy>>>,
    pub original_ids: Vec<usize>,
    pub time_to_nodes: HashMap<i64, Vec<usize>>,
    pub dep_to_edges: HashMap<u32, Vec<usize>>,
    pub prov_to_edges: HashMap<u32, Vec<usize>>,
}

#[derive(Debug, Clone)]
pub struct ViewableGraph {
    pub dpdg: ExportablePDG,
    pub shown_ids: HashSet<usize>,
    pub time_to_nodes: HashMap<i64, Vec<usize>>,
    pub dep_to_edges: HashMap<u32, Vec<usize>>,
    pub prov_to_edges: HashMap<u32, Vec<usize>>,
    pub n_timestamps: u64,
    pub source_files: HashMap<String, Vec<String>>,
    pub should_group_nodes: bool,
    pub node_hierarchy: Option<Vec<Arc<RwLock<GraphNodeHierarchy>>>>,
    pub node_hierarchy_lookup: Option<HashMap<usize, Arc<RwLock<GraphNodeHierarchy>>>>,
    pub current_hier_dpdg: Option<HierarchicalGraph>
}
