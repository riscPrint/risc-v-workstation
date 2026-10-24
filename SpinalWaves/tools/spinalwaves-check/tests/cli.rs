//! End-to-end tests of the spinalwaves-check binary on small HGLDD/VCD fixtures:
//! a Vec of Bundles with an enum field, a nested (2-D) Vec, and the failure cases.

use std::path::{Path, PathBuf};
use std::process::Command;

const HGLDD: &str = r#"{
  "HGLDD": { "version": "1.0", "file_info": ["/abs/Top.scala"] },
  "objects": [
    { "kind": "struct", "obj_name": "Top_io_v", "source_lang_type_info": { "type_name": "Elem" },
      "port_vars": [
        { "var_name": "x", "type_name": "logic", "source_lang_type_info": { "type_name": "Bool" } },
        { "var_name": "e", "type_name": "logic", "packed_range": [1, 0], "enum_def_ref": 0,
          "source_lang_type_info": { "type_name": "State" } }
      ] },
    { "kind": "struct", "obj_name": "Top_io", "source_lang_type_info": { "type_name": "TopIo" },
      "port_vars": [
        { "var_name": "a", "type_name": "logic", "packed_range": [3, 0], "source_lang_type_info": { "type_name": "UInt(4 bits)" } },
        { "var_name": "v", "type_name": "Top_io_v", "unpacked_range": [1, 0], "source_lang_type_info": { "type_name": "Vec[Elem]" } }
      ] },
    { "kind": "module", "obj_name": "Top", "module_name": "Top", "source_lang_type_info": { "type_name": "Top" },
      "enum_defs": { "0": { "0": "Idle", "1": "Run", "2": "Done" } },
      "port_vars": [
        { "var_name": "clk", "value": { "sig_name": "clk" }, "type_name": "logic" },
        { "var_name": "io", "type_name": "Top_io",
          "value": { "opcode": "'{", "operands": [
            { "sig_name": "io_a" },
            { "opcode": "'{", "operands": [
              { "opcode": "'{", "operands": [ { "sig_name": "io_v_0_x" }, { "sig_name": "io_v_0_e" } ] },
              { "opcode": "'{", "operands": [ { "sig_name": "io_v_1_x" }, { "sig_name": "io_v_1_e" } ] }
            ] }
          ] } },
        { "var_name": "m", "type_name": "logic", "packed_range": [1, 0], "unpacked_range": [1, 0, 2, 0],
          "value": { "opcode": "'{", "operands": [
            { "opcode": "'{", "operands": [ { "sig_name": "m_0_0" }, { "sig_name": "m_0_1" }, { "sig_name": "m_0_2" } ] },
            { "opcode": "'{", "operands": [ { "sig_name": "m_1_0" }, { "sig_name": "m_1_1" }, { "sig_name": "m_1_2" } ] }
          ] } }
        DROPPED
      ],
      "children": [] }
  ]
}
"#;

/// (name, width) of the VCD variables in scope TOP.Top.
const VARS: &[(&str, u32)] = &[
    ("clk", 1),
    ("io_a", 4),
    ("io_v_0_x", 1),
    ("io_v_0_e", 2),
    ("io_v_1_x", 1),
    ("io_v_1_e", 2),
    ("m_0_0", 2),
    ("m_0_1", 2),
    ("m_0_2", 2),
    ("m_1_0", 2),
    ("m_1_1", 2),
    ("m_1_2", 2),
];

fn vcd(vars: &[(&str, u32)]) -> String {
    let mut s = String::from("$timescale 1 ps $end\n$scope module TOP $end\n$scope module Top $end\n");
    let codes: Vec<String> = (0..vars.len()).map(|i| ((b'!' + i as u8) as char).to_string()).collect();
    for ((name, w), code) in vars.iter().zip(&codes) {
        if *w == 1 {
            s += &format!("$var wire 1 {code} {name} $end\n");
        } else {
            s += &format!("$var wire {w} {code} {name} [{}:0] $end\n", w - 1);
        }
    }
    s += "$upscope $end\n$upscope $end\n$enddefinitions $end\n";
    for t in [0, 10] {
        s += &format!("#{t}\n");
        for ((_, w), code) in vars.iter().zip(&codes) {
            let bit = if t == 0 { '0' } else { '1' };
            if *w == 1 {
                s += &format!("{bit}{code}\n");
            } else {
                s += &format!("b{} {code}\n", bit.to_string().repeat(*w as usize));
            }
        }
    }
    s
}

struct Case {
    dir: PathBuf,
}

impl Case {
    fn new(name: &str, hgldd: &str, vcd_text: &str) -> Self {
        let dir = Path::new(env!("CARGO_TARGET_TMPDIR")).join(name);
        let _ = std::fs::remove_dir_all(&dir);
        std::fs::create_dir_all(dir.join("hgldd")).unwrap();
        std::fs::write(dir.join("hgldd/Top.dd"), hgldd).unwrap();
        std::fs::write(dir.join("wave.vcd"), vcd_text).unwrap();
        Case { dir }
    }

    /// Run with `<wave.vcd> --hgldd-dir <dir> --json <report> <extra args>`; return (exit code, report).
    fn run(&self, extra: &[&str]) -> (i32, serde_json::Value) {
        let json = self.dir.join("report.json");
        let _ = std::fs::remove_file(&json);
        let out = Command::new(env!("CARGO_BIN_EXE_spinalwaves-check"))
            .arg(self.dir.join("wave.vcd"))
            .arg("--hgldd-dir")
            .arg(self.dir.join("hgldd"))
            .arg("--json")
            .arg(&json)
            .args(extra)
            .output()
            .unwrap();
        let code = out.status.code().unwrap();
        let report = std::fs::read_to_string(&json)
            .map(|s| serde_json::from_str(&s).unwrap())
            .unwrap_or(serde_json::Value::Null);
        if code != 0 {
            eprintln!("{}", String::from_utf8_lossy(&out.stdout));
            eprintln!("{}", String::from_utf8_lossy(&out.stderr));
        }
        (code, report)
    }
}

const SCOPES: &[&str] = &["--top-module", "Top", "--extra-scopes", "TOP", "Top"];

fn hgldd() -> String {
    HGLDD.replace("DROPPED", "")
}

fn error_kinds(report: &serde_json::Value) -> Vec<(String, String)> {
    report["errors"]
        .as_array()
        .unwrap()
        .iter()
        .map(|e| (e["kind"].as_str().unwrap().to_string(), e["typed_path"].as_str().unwrap().to_string()))
        .collect()
}

#[test]
fn pass_vec_of_bundles_nested_vec_enum() {
    let case = Case::new("pass", &hgldd(), &vcd(VARS));
    let (code, report) = case.run(SCOPES);
    assert_eq!(code, 0);
    assert_eq!(report["ok"], true);
    assert_eq!(report["counts"]["leaves"], 12);
    assert_eq!(report["counts"]["resolved"], 12);
    assert_eq!(report["counts"]["uncovered"], 0);

    // Rewritten VCD: one aggregate `io` (4 + 2 * (1 + 2) = 10 bits) and `m` (6 * 2 = 12 bits).
    let rewritten = case.dir.join("wave.tywaves.vcd");
    assert_eq!(report["rewritten_vcd"], rewritten.display().to_string());
    let text = std::fs::read_to_string(&rewritten).unwrap();
    assert!(text.contains(" 10 ") && text.contains(" io [9:0] "), "{text}");
    assert!(text.contains(" m [11:0] "), "{text}");
}

#[test]
fn missing_trace_is_fatal() {
    let vars: Vec<_> = VARS.iter().copied().filter(|(n, _)| *n != "io_v_1_e").collect();
    let case = Case::new("missing", &hgldd(), &vcd(&vars));
    let (code, report) = case.run(SCOPES);
    assert_eq!(code, 1);
    assert_eq!(report["counts"]["missing"], 1);
    assert_eq!(error_kinds(&report), vec![("missing_trace".into(), "TOP.Top.io.v.1.e".into())]);
    assert_eq!(report["errors"][0]["vcd_path"], "TOP.Top.io_v_1_e");
}

#[test]
fn width_mismatch_is_fatal() {
    let vars: Vec<_> = VARS.iter().map(|&(n, w)| if n == "m_1_2" { (n, 3) } else { (n, w) }).collect();
    let case = Case::new("width", &hgldd(), &vcd(&vars));
    let (code, report) = case.run(&[SCOPES, &["--no-rewrite"]].concat());
    assert_eq!(code, 1);
    assert_eq!(error_kinds(&report), vec![("width_mismatch".into(), "TOP.Top.m.1.2".into())]);
}

#[test]
fn wrong_scopes_are_reported() {
    let case = Case::new("scopes", &hgldd(), &vcd(VARS));
    let (code, report) = case.run(&["--top-module", "Nope", "--extra-scopes", "TOP", "Top", "--no-rewrite"]);
    assert_eq!(code, 1);
    assert_eq!(error_kinds(&report)[0], ("top_module_not_found".into(), "Nope".into()));

    let (code, report) = case.run(&["--no-rewrite"]); // no extra scopes: VCD has TOP.Top, not Top
    assert_eq!(code, 1);
    assert_eq!(error_kinds(&report)[0], ("missing_scope".into(), "Top".into()));
}

#[test]
fn dropped_variable_is_fatal_unless_allowed() {
    let dropped = HGLDD.replace(
        "DROPPED",
        r#", { "var_name": "pruned", "type_name": "logic", "packed_range": [7, 0] }"#,
    );
    let case = Case::new("dropped", &dropped, &vcd(VARS));
    let (code, report) = case.run(&[SCOPES, &["--no-rewrite"]].concat());
    assert_eq!(code, 1);
    assert_eq!(error_kinds(&report), vec![("dropped_no_value".into(), "Top.pruned".into())]);

    let (code, report) = case.run(&[SCOPES, &["--no-rewrite", "--allow-dropped"]].concat());
    assert_eq!(code, 0);
    assert_eq!(report["warnings"][0]["kind"], "dropped_no_value");
}

#[test]
fn input_errors_exit_2() {
    let case = Case::new("errors", &hgldd(), &vcd(VARS));
    std::fs::remove_file(case.dir.join("wave.vcd")).unwrap();
    let (code, _) = case.run(SCOPES);
    assert_eq!(code, 2);

    let case = Case::new("bad-json", "{ not json", &vcd(VARS));
    let (code, _) = case.run(SCOPES);
    assert_eq!(code, 2);
}

#[test]
fn empty_dataset_is_fatal() {
    let empty = r#"{ "HGLDD": { "version": "1.0", "file_info": [] },
      "objects": [ { "kind": "module", "obj_name": "Top", "module_name": "Top", "port_vars": [], "children": [] } ] }"#;
    let case = Case::new("empty", empty, &vcd(VARS));
    let (code, report) = case.run(&[SCOPES, &["--no-rewrite"]].concat());
    assert_eq!(code, 1);
    assert_eq!(error_kinds(&report), vec![("no_typed_leaves".into(), "".into())]);
}

#[test]
fn deduplicated_module_with_instance_overrides() {
    let hgldd = r#"{ "HGLDD": { "version": "1.0", "file_info": [] },
      "objects": [
        { "kind": "struct", "obj_name": "FlatChild_io", "port_vars": [
            { "var_name": "a_b", "type_name": "logic", "packed_range": [3, 0] } ] },
        { "kind": "struct", "obj_name": "NestedChild_io_a", "port_vars": [
            { "var_name": "b", "type_name": "logic", "packed_range": [3, 0] } ] },
        { "kind": "struct", "obj_name": "NestedChild_io", "port_vars": [
            { "var_name": "a", "type_name": "NestedChild_io_a" } ] },
        { "kind": "module", "obj_name": "FlatChild", "module_name": "Child",
          "port_vars": [ { "var_name": "io", "type_name": "FlatChild_io",
            "value": { "opcode": "'{", "operands": [ { "sig_name": "io_a_b" } ] } } ] },
        { "kind": "module", "obj_name": "Top", "module_name": "Top",
          "port_vars": [ { "var_name": "clk", "type_name": "logic", "value": { "sig_name": "clk" } } ],
          "children": [
            { "name": "f1", "obj_name": "FlatChild", "module_name": "Child" },
            { "name": "n1", "obj_name": "FlatChild", "module_name": "Child",
              "source_lang_type_info": { "type_name": "NestedChild" },
              "port_vars": [ { "var_name": "io", "type_name": "NestedChild_io",
                "value": { "opcode": "'{", "operands": [ { "opcode": "'{", "operands": [ { "sig_name": "io_a_b" } ] } ] } } ] } ] } ] }"#;
    let vcd_text = "$timescale 1 ps $end\n$scope module TOP $end\n$scope module Top $end\n\
        $var wire 1 ! clk $end\n\
        $scope module f1 $end\n$var wire 4 \" io_a_b [3:0] $end\n$upscope $end\n\
        $scope module n1 $end\n$var wire 4 # io_a_b [3:0] $end\n$upscope $end\n\
        $upscope $end\n$upscope $end\n$enddefinitions $end\n#0\n0!\nb0001 \"\nb0010 #\n#10\n1!\n";
    let case = Case::new("overrides", hgldd, vcd_text);
    let (code, report) = case.run(&["-v", "--top-module", "Top", "--extra-scopes", "TOP", "Top"]);
    assert_eq!(code, 0);
    assert_eq!(report["counts"]["leaves"], 3);
    assert_eq!(report["counts"]["resolved"], 3);

    // An override variable without a value is reported, not dropped silently.
    let dropped = hgldd.replace(
        r#""source_lang_type_info": { "type_name": "NestedChild" },"#,
        r#""source_lang_type_info": { "type_name": "NestedChild" }, "children": [],"#,
    )
    .replace(
        r#"{ "var_name": "io", "type_name": "NestedChild_io","#,
        r#"{ "var_name": "lost", "type_name": "logic" }, { "var_name": "io", "type_name": "NestedChild_io","#,
    );
    let case = Case::new("overrides-dropped", &dropped, vcd_text);
    let (code, report) = case.run(&["--no-rewrite", "--top-module", "Top", "--extra-scopes", "TOP", "Top"]);
    assert_eq!(code, 1);
    assert_eq!(error_kinds(&report), vec![("dropped_no_value".into(), "Top.n1.lost".into())]);
}
