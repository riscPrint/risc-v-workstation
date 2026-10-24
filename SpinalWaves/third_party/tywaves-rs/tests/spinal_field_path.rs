//! SpinalWaves patch: `find_trace` resolves typed field paths (`scope... var field...`).

use std::path::Path;

use tywaves_rs::hgldd;
use tywaves_rs::tyvcd::builder::{GenericBuilder, TyVcdBuilder};
use tywaves_rs::tyvcd::spec::{TyVcd, Variable};
use tywaves_rs::tyvcd::trace_pointer::{TraceFinder, TraceValue};

fn build(file: &str) -> TyVcd {
    let hgldd = hgldd::reader::parse_hgldd_file(Path::new(file)).expect("parse");
    let mut builder = TyVcdBuilder::init(hgldd);
    builder.build().expect("build");
    builder.get_copy().unwrap()
}

fn trace_name_at(tyvcd: &TyVcd, path: &[&str]) -> Option<TraceValue> {
    let path: Vec<String> = path.iter().map(|s| s.to_string()).collect();
    let found = tyvcd.find_trace(&path)?;
    let found = found.read().unwrap();
    let var = found.as_any().downcast_ref::<Variable>()?;
    Some(var.get_trace_value_pub())
}

trait TraceValuePub {
    fn get_trace_value_pub(&self) -> TraceValue;
}
impl TraceValuePub for Variable {
    fn get_trace_value_pub(&self) -> TraceValue {
        use tywaves_rs::tyvcd::trace_pointer::TraceGetter;
        self.get_trace_value().clone()
    }
}

fn sig(s: &str) -> Option<TraceValue> {
    Some(TraceValue::RefTraceName(s.to_string()))
}

#[test]
fn field_paths_resolve() {
    let t = build("tests/inputs/tyvcd/withBundlesAndVecs.dd");
    let top = "WithBundlesAndVecs";
    assert_eq!(trace_name_at(&t, &[top, "io", "a"]), sig("io_a_0"));
    assert_eq!(trace_name_at(&t, &[top, "io", "b", "a"]), sig("io_b_a_0"));
    assert_eq!(trace_name_at(&t, &[top, "io", "b", "b", "vec", "0"]), sig("io_b_b_vec_0_0"));
    assert_eq!(trace_name_at(&t, &[top, "io", "b", "b", "vec", "1"]), sig("io_b_b_vec_1_0"));
    assert_eq!(trace_name_at(&t, &[top, "io", "vec", "1", "x"]), sig("io_vec_1_x_0"));
    assert_eq!(trace_name_at(&t, &[top, "io", "vec", "1", "y", "z"]), sig("io_vec_1_y_z_0"));
    // Upstream lookups keep working: top variable by name and leaf by trace name.
    assert!(trace_name_at(&t, &[top, "io"]).is_some());
    assert_eq!(trace_name_at(&t, &[top, "io_vec_0_y_z_0"]), sig("io_vec_0_y_z_0"));
    // Unknown fields / too deep paths are not found.
    assert_eq!(trace_name_at(&t, &[top, "io", "nope"]), None);
    assert_eq!(trace_name_at(&t, &[top, "io", "a", "0"]), None);
    assert_eq!(trace_name_at(&t, &[top, "io", "vec", "2"]), None);
}
