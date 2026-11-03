use std::sync::RwLock;

use clap::Parser;
use anyhow::Result;
use spinaltrace_rs::graphbuilder::GraphProcessingType;

use app_state::{AppState, PDGConfig};
use graph_building::{make_dpdg, get_trace_accuracy};
use graph_interaction::{get_n_timeslots, get_partial_graph, toggle_module, set_new_head, reset_head, open_vs_code};

mod argument_parsing;
mod errors;
mod graph_building;
mod app_state;
mod graph_interaction;
mod translation;

#[tauri::command]
fn get_initial_route() -> String {
    "/loading_screen".into()
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() -> Result<()> {
    let args = argument_parsing::Args::parse().validate()?;
    let mut state = AppState::new();
    state.pdg_config = Some(PDGConfig {
        request: args.request(GraphProcessingType::Normal),
        group_nodes: args.hier_grouping.unwrap_or(false),
    });

    tauri::Builder::default()
        .plugin(tauri_plugin_opener::init())
        .manage(RwLock::new(state))
        .invoke_handler(tauri::generate_handler![get_initial_route, get_trace_accuracy, make_dpdg, get_n_timeslots, get_partial_graph, toggle_module, set_new_head, reset_head, open_vs_code])
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
    Ok(())
}
