use spinaltrace_rs::{conversion::pdg_convert_to_source, pdg_spec::{ExportablePDG, PDGSpec, TraceAccuracy}};
fn spec() -> PDGSpec {
    serde_json::from_value(serde_json::json!({"vertices": [], "edges": [], "predicates": [], "cfg": [],
        "spinaltrace": {"formatVersion": 2, "clockDomains": []}})).unwrap()
}
#[test]
fn legacy_extraction_is_incomplete() {
    let mut p = spec();
    p.spinaltrace.as_mut().unwrap().format_version = 1;
    assert_eq!(TraceAccuracy::from_spec(&p).status, "incomplete");
    p.spinaltrace = None;
    assert_eq!(ExportablePDG::from(p).accuracy.status, "incomplete");
}
#[test]
fn unmodeled_clock_semantics_are_incomplete_without_warning_text() {
    for domains in [serde_json::json!([{"clock":"a"}, {"clock":"b"}]),
        serde_json::json!([{"clock":"a", "clockEnable":"en"}]),
        serde_json::json!([{"clock":"a", "softReset":"soft"}])] {
        let mut value = serde_json::to_value(spec()).unwrap();
        value["spinaltrace"]["clockDomains"] = domains;
        let p: PDGSpec = serde_json::from_value(value).unwrap();
        assert_eq!(TraceAccuracy::from_spec(&p).status, "incomplete");
    }
}
#[test]
fn extraction_warnings_survive_conversion() {
    for reason in ["unsupported switch key; that case is never taken", "anonymous expression; both inputs count"] {
        let mut p = spec();
        p.spinaltrace.as_mut().unwrap().warnings.push(reason.into());
        let converted = pdg_convert_to_source(p.into(), false, false);
        let json = serde_json::to_value(converted).unwrap();
        assert_eq!(json["accuracy"]["status"], "incomplete");
        assert!(json["accuracy"]["reasons"].as_array().unwrap().iter().any(|v| v == reason));
    }
}
#[test]
fn source_grouping_is_never_exact_and_status_round_trips() {
    let graph = pdg_convert_to_source(spec().into(), false, false);
    assert_eq!(graph.accuracy.status, "approximate");
    let copy: ExportablePDG = serde_json::from_str(&serde_json::to_string(&graph).unwrap()).unwrap();
    assert_eq!(copy.accuracy, graph.accuracy);
    assert_eq!(serde_json::from_str::<ExportablePDG>("{\"vertices\":[],\"edges\":[]}").unwrap().accuracy.status, "incomplete");
}
#[test]
fn partial_write_limits_are_explicit() {
    let fixture = std::path::Path::new(env!("CARGO_MANIFEST_DIR")).join("tests/fixtures/sync_mem/pdg.json");
    let mut p: PDGSpec = serde_json::from_reader(std::fs::File::open(fixture).unwrap()).unwrap();
    p.spinaltrace = spec().spinaltrace;
    p.vertices[0].assign_range = Some("dyn".into());
    let a = TraceAccuracy::from_spec(&p);
    assert_eq!(a.status, "incomplete");
    assert!(a.reasons.iter().any(|r| r.contains("16 providers")));
}

#[test]
fn missing_predicate_is_not_an_exact_replay() {
    use spinaltrace_rs::{graphbuilder::CriterionType, pipeline::{self, TraceRequest}};
    let root = std::path::Path::new(env!("CARGO_MANIFEST_DIR")).join("tests/fixtures/gcd");
    let mut p: PDGSpec = serde_json::from_reader(std::fs::File::open(root.join("pdg.json")).unwrap()).unwrap();
    p.spinaltrace.as_mut().unwrap().format_version = 2;
    p.predicates[0].name = "missing_predicate".into();
    let path = std::env::temp_dir().join(format!("trace-accuracy-{}.json", std::process::id()));
    std::fs::write(&path, serde_json::to_vec(&p).unwrap()).unwrap();
    let mut req = TraceRequest::new(&path, root.join("wave.vcd"), CriterionType::Signal("io_result".into()));
    req.convert_to_source = false;
    req.raw_values = false;
    let graph = pipeline::trace(&req).unwrap();
    std::fs::remove_file(path).unwrap();
    assert_eq!(graph.accuracy.status, "incomplete");
    assert!(graph.accuracy.reasons.iter().any(|r| r.contains("missing_predicate")));
}

#[test]
fn disabling_a_design_reset_is_incomplete() {
    use spinaltrace_rs::{graphbuilder::CriterionType, pipeline::{self, TraceRequest}};
    let root = std::path::Path::new(env!("CARGO_MANIFEST_DIR")).join("tests/fixtures/gcd");
    let mut req = TraceRequest::new(root.join("pdg.json"), root.join("wave.vcd"), CriterionType::Signal("io_result".into()));
    req.no_reset = true;
    req.raw_values = false;
    let graph = pipeline::trace(&req).unwrap();
    assert!(graph.accuracy.reasons.iter().any(|r| r.contains("Reset replay was disabled")));
}

#[test]
fn explicit_extraction_accuracy_cannot_improve_during_conversion() {
    let mut p = spec();
    let mut accuracy = TraceAccuracy::exact();
    accuracy.report("incomplete", "Unknown source cause from extraction.");
    p.accuracy = Some(accuracy);
    let graph = pdg_convert_to_source(p.into(), false, false);
    assert_eq!(graph.accuracy.status, "incomplete");
    assert!(graph.accuracy.reasons.iter().any(|r| r.contains("Unknown source cause")));
}

#[test]
fn unknown_switch_values_are_incomplete() {
    use spinaltrace_rs::{graphbuilder::CriterionType, pipeline::{self, TraceRequest}};
    let root = std::path::Path::new(env!("CARGO_MANIFEST_DIR")).join("tests/fixtures/switch_enum");
    let text = std::fs::read_to_string(root.join("wave.vcd")).unwrap();
    let text = text.lines().map(|line| {
        if line.starts_with('b') {
            let (_, id) = line.split_once(' ').unwrap();
            format!("bx {}", id)
        } else { line.into() }
    }).collect::<Vec<String>>().join("\n");
    let path = std::env::temp_dir().join(format!("trace-unknown-{}.vcd", std::process::id()));
    std::fs::write(&path, text + "\n").unwrap();
    let mut req = TraceRequest::new(root.join("pdg.json"), &path, CriterionType::Signal("io_result".into()));
    req.raw_values = false;
    let graph = pipeline::trace(&req).unwrap();
    std::fs::remove_file(path).unwrap();
    assert!(graph.accuracy.reasons.iter().any(|r| r.contains("unknown VCD value")));
}

#[test]
fn missing_reset_is_an_error() {
    use spinaltrace_rs::{graphbuilder::CriterionType, pipeline::{self, TraceRequest}};
    let root = std::path::Path::new(env!("CARGO_MANIFEST_DIR")).join("tests/fixtures/gcd");
    let mut req = TraceRequest::new(root.join("pdg.json"), root.join("wave.vcd"), CriterionType::Signal("io_result".into()));
    req.reset = Some("missing_reset".into());
    assert!(pipeline::trace(&req).unwrap_err().to_string().contains("missing_reset"));
}

#[test]
fn static_slice_keeps_design_wide_limits() {
    let root = std::path::Path::new(env!("CARGO_MANIFEST_DIR")).join("tests/fixtures/gcd/pdg.json");
    let mut p: PDGSpec = serde_json::from_reader(std::fs::File::open(root).unwrap()).unwrap();
    let mut accuracy = TraceAccuracy::exact();
    accuracy.report("incomplete", "A cause outside this slice is unknown.");
    p.accuracy = Some(accuracy);
    let sliced = spinaltrace_rs::slicing::pdg_slice(p, "connect_x").unwrap();
    assert!(TraceAccuracy::from_spec(&sliced).reasons.iter().any(|r| r.contains("outside this slice")));
}
