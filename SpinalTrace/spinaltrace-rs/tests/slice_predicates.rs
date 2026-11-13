//! Static slices must keep predicate indexes valid for dynamic replay.
use spinaltrace_rs::{pdg_spec::PDGSpec, slicing::pdg_slice};
use serde_json::json;

#[test]
fn removed_fork_does_not_shift_the_retained_predicate() {
    let vertex = |name: &str| json!({"file":"Test.scala", "line":1,"char":0,"name":name,
        "kind":"ControlFlow","clocked":false,"isChiselStatement":true});
    let pdg: PDGSpec = serde_json::from_value(json!({
        "vertices":[vertex("unused"),vertex("retained")], "edges":[],
        "predicates":[vertex("unused_pred"),vertex("retained_pred")],
        "cfg":[{"stmtRef":0,"predStmtRef":0},{"stmtRef":1,"predStmtRef":1}]
    })).unwrap();
    let sliced = pdg_slice(pdg, "retained").unwrap();
    let pred = sliced.cfg[0].pred_stmt_ref.unwrap() as usize;
    assert_eq!(sliced.predicates[pred].name, "retained_pred");
}
