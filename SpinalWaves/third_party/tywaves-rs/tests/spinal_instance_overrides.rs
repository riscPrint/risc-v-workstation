//! SpinalWaves patch: per-instance `port_vars` / `children` / `source_lang_type_info`.
//!
//! SpinalHDL deduplicates components with identical RTL, so one HGLDD module object (`Child`)
//! stands for instances whose Scala types differ: `FlatChild` has `io.a_b`, `NestedChild` has
//! `io.a.b`, both are RTL signal `io_a_b`. The instance overrides must apply to that instance
//! only, recursively, and never leak to siblings.

use tywaves_rs::hgldd;
use tywaves_rs::tyvcd::builder::{GenericBuilder, TyVcdBuilder};
use tywaves_rs::tyvcd::spec::{Scope, TyVcd, Variable};
use tywaves_rs::tyvcd::trace_pointer::{TraceFinder, TraceGetter, TraceValue};

const HGLDD: &str = r#"
{ "HGLDD": { "version": "1.0", "file_info": ["/abs/Top.scala"] },
  "objects": [
    { "kind": "struct", "obj_name": "FlatChild_io", "port_vars": [
        { "var_name": "a_b", "type_name": "logic", "packed_range": [3, 0] } ] },
    { "kind": "struct", "obj_name": "NestedChild_io_a", "port_vars": [
        { "var_name": "b", "type_name": "logic", "packed_range": [3, 0] } ] },
    { "kind": "struct", "obj_name": "NestedChild_io", "port_vars": [
        { "var_name": "a", "type_name": "NestedChild_io_a" } ] },
    { "kind": "module", "obj_name": "Leaf", "module_name": "Leaf",
      "source_lang_type_info": { "type_name": "Leaf" },
      "port_vars": [ { "var_name": "x", "type_name": "logic", "value": { "sig_name": "x" } } ] },
    { "kind": "module", "obj_name": "FlatChild", "module_name": "Child",
      "source_lang_type_info": { "type_name": "FlatChild", "params": [ { "name": "w", "type": "Int", "value": "4" } ] },
      "port_vars": [
        { "var_name": "io", "type_name": "FlatChild_io", "value": { "opcode": "'{", "operands": [ { "sig_name": "io_a_b" } ] } } ],
      "children": [ { "name": "leaf", "obj_name": "Leaf", "module_name": "Leaf" } ] },
    { "kind": "module", "obj_name": "Top", "module_name": "Top",
      "port_vars": [ { "var_name": "clk", "type_name": "logic", "value": { "sig_name": "clk" } } ],
      "children": [
        { "name": "f1", "obj_name": "FlatChild", "module_name": "Child" },
        { "name": "n1", "obj_name": "FlatChild", "module_name": "Child",
          "source_lang_type_info": { "type_name": "NestedChild", "params": [ { "name": "depth", "type": "Int", "value": "2" } ] },
          "port_vars": [
            { "var_name": "io", "type_name": "NestedChild_io",
              "value": { "opcode": "'{", "operands": [ { "opcode": "'{", "operands": [ { "sig_name": "io_a_b" } ] } ] } } ],
          "children": [
            { "name": "leaf", "obj_name": "Leaf", "module_name": "Leaf",
              "source_lang_type_info": { "type_name": "LeafB" },
              "port_vars": [ { "var_name": "y", "type_name": "logic", "value": { "sig_name": "x" } } ] } ] },
        { "name": "e1", "obj_name": "FlatChild", "module_name": "Child", "port_vars": [], "children": [] }
      ] }
  ] }
"#;

fn build(extra: Option<(&[&str], &str)>) -> TyVcd {
    let hgldds = hgldd::reader::parse_hgldds(HGLDD).expect("parse");
    let mut builder = TyVcdBuilder::init(hgldds);
    if let Some((scopes, top)) = extra {
        builder = builder.with_extra_artifact_scopes(scopes.iter().map(|s| s.to_string()).collect(), &top.to_string());
    }
    builder.build().expect("build");
    builder.get_copy().unwrap()
}

fn path(p: &[&str]) -> Vec<String> {
    p.iter().map(|s| s.to_string()).collect()
}

fn leaf(t: &TyVcd, p: &[&str]) -> Option<TraceValue> {
    let found = t.find_trace(&path(p))?;
    let found = found.read().unwrap();
    found.as_any().downcast_ref::<Variable>().map(|v| v.get_trace_value().clone())
}

/// (type name, param names, variable names, subscope names) of a scope.
fn scope_info(t: &TyVcd, p: &[&str]) -> (String, Vec<String>, Vec<String>, Vec<String>) {
    let found = t.find_trace(&path(p)).expect("scope");
    let found = found.read().unwrap();
    let s = found.as_any().downcast_ref::<Scope>().expect("is a scope");
    let mut subs: Vec<String> = s.subscopes.keys().cloned().collect();
    subs.sort();
    (
        s.high_level_info.type_name.clone(),
        s.high_level_info.params.iter().map(|p| p.name.clone()).collect(),
        s.variables.iter().map(|v| v.name.clone()).collect(),
        subs,
    )
}

fn sig(s: &str) -> Option<TraceValue> {
    Some(TraceValue::RefTraceName(s.to_string()))
}

fn check(t: &TyVcd, top: &[&'static str]) {
    let at = |rest: &[&'static str]| -> Vec<&'static str> { [top, rest].concat() };

    // f1: canonical definition.
    assert_eq!(leaf(t, &at(&["f1", "io", "a_b"])), sig("io_a_b"));
    assert_eq!(leaf(t, &at(&["f1", "io", "a", "b"])), None);
    assert_eq!(
        scope_info(t, &at(&["f1"])),
        ("FlatChild".into(), vec!["w".into()], vec!["io".into()], vec!["leaf".into()])
    );
    assert_eq!(scope_info(t, &at(&["f1", "leaf"])), ("Leaf".into(), vec![], vec!["x".into()], vec![]));

    // n1: same RTL module, its own typed vars, type info and nested child override.
    assert_eq!(leaf(t, &at(&["n1", "io", "a", "b"])), sig("io_a_b"));
    assert_eq!(leaf(t, &at(&["n1", "io", "a_b"])), None);
    assert_eq!(
        scope_info(t, &at(&["n1"])),
        ("NestedChild".into(), vec!["depth".into()], vec!["io".into()], vec!["leaf".into()])
    );
    assert_eq!(scope_info(t, &at(&["n1", "leaf"])), ("LeafB".into(), vec![], vec!["y".into()], vec![]));
    assert_eq!(leaf(t, &at(&["n1", "leaf", "y"])), sig("x"));

    // e1: explicit empty port_vars and children.
    assert_eq!(scope_info(t, &at(&["e1"])), ("FlatChild".into(), vec!["w".into()], vec![], vec![]));
}

#[test]
fn instance_overrides_apply_per_instance() {
    let t = build(None);
    assert_eq!(t.scopes.len(), 1);
    check(&t, &["Top"]);
}

#[test]
fn instance_overrides_with_extra_scopes() {
    let t = build(Some((&["TOP", "Top"], "Top")));
    assert_eq!(t.scopes.len(), 1);
    check(&t, &["TOP", "Top"]);
}

#[test]
fn overrides_do_not_leak_into_module_definitions() {
    // Building twice from the same input gives the same result (no shared state mutated).
    let a = build(None);
    let b = build(None);
    assert!(a == b);
    // The scope paths of the deep copies follow the instance names.
    let n1_leaf = a.find_trace(&path(&["Top", "n1", "leaf"])).unwrap();
    assert_eq!(n1_leaf.read().unwrap().get_trace_path(), &path(&["Top", "n1", "leaf"]));
}
