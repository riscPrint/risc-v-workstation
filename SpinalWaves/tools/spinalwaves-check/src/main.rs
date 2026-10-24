//! spinalwaves-check: load a SpinalWaves HGLDD with tywaves-rs, build the TyVcd with the given
//! extra scopes / top module, check that every typed leaf resolves to a trace in the VCD, and
//! rewrite the VCD the same way surfer-tywaves does.
//!
//! Exit codes: 0 = all checks passed, 1 = verification failed, 2 = usage/input/build error.

use std::collections::HashSet;
use std::fs::File;
use std::io::BufReader;
use std::panic::{catch_unwind, AssertUnwindSafe};
use std::path::{Path, PathBuf};
use std::process::ExitCode;

use clap::Parser;
use serde::Serialize;

use tywaves_rs::hgldd::{self, spec::Hgldd, spec::ObjectKind};
use tywaves_rs::tyvcd::builder::{GenericBuilder, TyVcdBuilder};
use tywaves_rs::tyvcd::spec::{ScopeDef, TyVcd, Variable, VariableKind};
use tywaves_rs::tyvcd::trace_pointer::{TraceFinder, TraceGetter, TraceValue};
use tywaves_rs::vcd_rewrite::VcdRewriter;

const EXIT_FAIL: u8 = 1;
const EXIT_ERROR: u8 = 2;

/// Check a SpinalWaves HGLDD against a VCD and rewrite the VCD for surfer-tywaves.
///
/// Every typed leaf (ground field of a module variable, recursively through bundles, vecs and
/// areas) must resolve to a VCD variable of the same width, and tywaves-rs `find_trace` must find
/// it from its typed path (scopes ++ variable ++ fields). Any missing trace is fatal (exit 1).
#[derive(Parser, Debug)]
#[command(name = "spinalwaves-check", version, verbatim_doc_comment)]
struct Args {
    /// Input VCD file (same as --vcd). Put it before --extra-scopes, which takes several values.
    #[arg(value_name = "VCD", conflicts_with = "vcd", required_unless_present = "vcd")]
    wave: Option<PathBuf>,

    /// Input VCD file.
    #[arg(long, value_name = "FILE")]
    vcd: Option<PathBuf>,

    /// HGLDD file (*.dd) or a directory containing *.dd files. Alias: --hgldd-dir.
    #[arg(long, visible_alias = "hgldd-dir", value_name = "FILE|DIR")]
    hgldd: PathBuf,

    /// VCD scopes above the HGLDD toplevel, outermost first, INCLUDING the DUT scope
    /// (e.g. `--extra-scopes TOP Top`). The last one replaces --top-module, exactly like
    /// surfer-tywaves --extra-scopes / tywaves-rs `with_extra_artifact_scopes`.
    #[arg(long, num_args(1..), value_name = "SCOPE", requires = "top_module")]
    extra_scopes: Vec<String>,

    /// HGLDD top module (obj_name or module_name) that the last extra scope replaces.
    #[arg(long, value_name = "NAME", requires = "extra_scopes")]
    top_module: Option<String>,

    /// Rewritten VCD path (must end in .vcd). Default: <vcd dir>/<vcd stem>.tywaves.vcd
    #[arg(short, long, value_name = "FILE")]
    out: Option<PathBuf>,

    /// Only check; do not write the rewritten VCD.
    #[arg(long)]
    no_rewrite: bool,

    /// Also write the report as JSON to this file.
    #[arg(long, value_name = "FILE")]
    json: Option<PathBuf>,

    /// Treat module variables without a value expression (silently dropped by the tywaves-rs
    /// builder) as warnings instead of errors.
    #[arg(long)]
    allow_dropped: bool,

    /// List VCD variables in typed scopes that no typed leaf refers to.
    #[arg(long)]
    list_uncovered: bool,

    /// Fail (exit 1) if any VCD variable in a typed scope is not referred to by a typed leaf.
    #[arg(long)]
    fail_on_uncovered: bool,

    /// Print every typed leaf with its VCD path and status.
    #[arg(short, long)]
    verbose: bool,

    /// Maximum number of errors/warnings printed (the JSON report always has all).
    #[arg(long, default_value_t = 50, value_name = "N")]
    max_report: usize,

    /// Print only errors and the final PASS/FAIL line.
    #[arg(short, long)]
    quiet: bool,
}

#[derive(Serialize, Debug, Clone)]
struct Issue {
    kind: &'static str,
    /// Typed path: VCD scopes ++ variable ++ fields, "." separated.
    typed_path: String,
    /// Expected VCD variable path, if any.
    #[serde(skip_serializing_if = "Option::is_none")]
    vcd_path: Option<String>,
    detail: String,
}

#[derive(Serialize, Default, Debug)]
struct Counts {
    hgldd_objects: usize,
    scopes: usize,
    scopes_missing: usize,
    variables: usize,
    leaves: usize,
    resolved: usize,
    constant: usize,
    missing: usize,
    width_mismatch: usize,
    unsupported: usize,
    find_trace_failed: usize,
    dropped: usize,
    uncovered: usize,
}

#[derive(Serialize, Default, Debug)]
struct Report {
    ok: bool,
    hgldd: String,
    vcd: String,
    extra_scopes: Vec<String>,
    top_module: Option<String>,
    rewritten_vcd: Option<String>,
    counts: Counts,
    errors: Vec<Issue>,
    warnings: Vec<Issue>,
    uncovered: Vec<String>,
}

struct Checker<'a> {
    tyvcd: &'a TyVcd,
    header: &'a vcd::Header,
    verbose: bool,
    report: Report,
    covered: HashSet<Vec<String>>,
    typed_scopes_in_vcd: Vec<Vec<String>>,
}

fn join(p: &[String]) -> String {
    p.join(".")
}

fn trace_value_str(v: &TraceValue) -> String {
    match v {
        TraceValue::RefTraceName(n) => format!("sig {n}"),
        TraceValue::Constant(c) => format!("const {c:?}"),
        TraceValue::RefTraceValues(vs) => format!("{} operands", vs.len()),
    }
}

/// Sorted (key, scope) pairs, for deterministic output.
fn sorted_scopes(
    m: &std::collections::HashMap<String, std::sync::Arc<std::sync::RwLock<ScopeDef>>>,
) -> Vec<(&String, &std::sync::Arc<std::sync::RwLock<ScopeDef>>)> {
    let mut v: Vec<_> = m.iter().collect();
    v.sort_by(|a, b| a.0.cmp(b.0));
    v
}

impl Checker<'_> {
    fn error(&mut self, kind: &'static str, typed: &[String], vcd: Option<&[String]>, detail: String) {
        self.report.errors.push(Issue { kind, typed_path: join(typed), vcd_path: vcd.map(join), detail });
    }
    fn warn(&mut self, kind: &'static str, typed: &[String], detail: String) {
        self.report.warnings.push(Issue { kind, typed_path: join(typed), vcd_path: None, detail });
    }

    fn walk_scope(&mut self, scope: &ScopeDef, path: &[String]) {
        self.report.counts.scopes += 1;
        let in_vcd = self.header.find_scope(path).is_some();
        if in_vcd {
            self.typed_scopes_in_vcd.push(path.to_vec());
        } else {
            self.report.counts.scopes_missing += 1;
            self.error(
                "missing_scope",
                path,
                Some(path),
                format!("scope (HGLDD module {}) not found in the VCD hierarchy", scope.name),
            );
        }
        for var in &scope.variables {
            self.report.counts.variables += 1;
            let mut typed = path.to_vec();
            typed.push(var.name.clone());
            self.walk_var(var, path, &mut typed, in_vcd);
        }
        for (key, sub) in sorted_scopes(&scope.subscopes) {
            let sub = sub.read().unwrap();
            let mut p = path.to_vec();
            p.push(key.clone());
            self.walk_scope(&sub, &p);
        }
    }

    fn walk_var(&mut self, var: &Variable, scope_path: &[String], typed: &mut Vec<String>, in_vcd: bool) {
        match &var.kind {
            VariableKind::Ground(w) => self.leaf(var, *w, scope_path, typed, in_vcd),
            VariableKind::External => self.warn(
                "external",
                typed,
                "variable has no type_name (External); not checked".into(),
            ),
            VariableKind::Struct { fields } | VariableKind::Vector { fields } => {
                if fields.is_empty() {
                    self.warn("empty_aggregate", typed, format!("{} has no fields", var.high_level_info.type_name));
                }
                for f in fields {
                    typed.push(f.name.clone());
                    self.walk_var(f, scope_path, typed, in_vcd);
                    typed.pop();
                }
            }
        }
    }

    fn leaf(&mut self, var: &Variable, width: u128, scope_path: &[String], typed: &[String], in_vcd: bool) {
        self.report.counts.leaves += 1;
        let tv = var.get_trace_value().clone();

        // 1. tywaves-rs find_trace on the typed path must return this leaf.
        let found = self.tyvcd.find_trace(typed).and_then(|t| {
            let t = t.read().unwrap();
            t.as_any().downcast_ref::<Variable>().map(|v| v.get_trace_value().clone())
        });
        match &found {
            Some(f) if *f == tv => {}
            Some(f) => {
                self.report.counts.find_trace_failed += 1;
                self.error(
                    "find_trace_mismatch",
                    typed,
                    None,
                    format!("find_trace returned a different leaf ({}), expected {}", trace_value_str(f), trace_value_str(&tv)),
                );
            }
            None => {
                self.report.counts.find_trace_failed += 1;
                self.error("find_trace_failed", typed, None, "tywaves-rs find_trace did not find this typed path".into());
            }
        }

        // 2. The leaf's trace must exist in the VCD with the same width.
        let status = match &tv {
            TraceValue::RefTraceName(name) => {
                let mut vcd_path = scope_path.to_vec();
                vcd_path.push(name.clone());
                if !in_vcd {
                    self.report.counts.missing += 1;
                    self.error("missing_trace", typed, Some(&vcd_path), "parent scope not in the VCD".into());
                    "MISSING (scope)".to_string()
                } else if let Some(v) = self.header.find_var(&vcd_path) {
                    let size = v.size as u128;
                    self.covered.insert(vcd_path.clone());
                    if width != size {
                        self.report.counts.width_mismatch += 1;
                        self.error(
                            "width_mismatch",
                            typed,
                            Some(&vcd_path),
                            format!("HGLDD width {width}, VCD width {size}"),
                        );
                        format!("WIDTH {width}!={size}")
                    } else {
                        self.report.counts.resolved += 1;
                        "ok".to_string()
                    }
                } else {
                    self.report.counts.missing += 1;
                    self.error(
                        "missing_trace",
                        typed,
                        Some(&vcd_path),
                        format!("no VCD variable `{name}` in scope {}", join(scope_path)),
                    );
                    "MISSING".to_string()
                }
            }
            TraceValue::Constant(_) => {
                self.report.counts.constant += 1;
                "constant".to_string()
            }
            TraceValue::RefTraceValues(vs) => {
                self.report.counts.unsupported += 1;
                self.error(
                    "unsupported_expression",
                    typed,
                    None,
                    format!("ground leaf has an operator value ({} operands); tywaves-rs renders it as 0", vs.len()),
                );
                "UNSUPPORTED".to_string()
            }
        };
        if self.verbose {
            println!("  {:<60} {:<40} [{width}] {status}", join(typed), trace_value_str(&tv));
        }
    }

    fn uncovered(&mut self) {
        for path in std::mem::take(&mut self.typed_scopes_in_vcd) {
            let Some(scope) = self.header.find_scope(&path) else { continue };
            for item in &scope.items {
                if let vcd::ScopeItem::Var(v) = item {
                    let mut p = path.clone();
                    p.push(v.reference.clone());
                    if !self.covered.contains(&p) {
                        self.report.uncovered.push(join(&p));
                    }
                }
            }
        }
        self.report.uncovered.sort();
        self.report.uncovered.dedup();
        self.report.counts.uncovered = self.report.uncovered.len();
    }
}

/// After the rewrite: every module variable must exist in the rewritten VCD and be found by
/// `find_trace(scopes ++ [reference])`, which is exactly how surfer-tywaves looks variables up.
fn check_rewritten(tyvcd: &TyVcd, out: &Path, report: &mut Report) -> Result<(), String> {
    let mut parser = vcd::Parser::new(BufReader::new(
        File::open(out).map_err(|e| format!("cannot open rewritten VCD {}: {e}", out.display()))?,
    ));
    let header = parser.parse_header().map_err(|e| format!("cannot parse rewritten VCD header: {e}"))?;

    fn walk(tyvcd: &TyVcd, header: &vcd::Header, scope: &ScopeDef, path: &[String], report: &mut Report) {
        for var in &scope.variables {
            let reference = var.get_trace_name().cloned().unwrap_or_else(|| var.name.clone());
            let mut p = path.to_vec();
            p.push(reference.clone());
            let mut typed = path.to_vec();
            typed.push(var.name.clone());
            if header.find_var(&p).is_none() {
                report.errors.push(Issue {
                    kind: "rewritten_missing",
                    typed_path: join(&typed),
                    vcd_path: Some(join(&p)),
                    detail: "variable not present in the rewritten VCD".into(),
                });
                continue;
            }
            let ok = tyvcd.find_trace(&p).is_some_and(|t| {
                let t = t.read().unwrap();
                t.as_any().downcast_ref::<Variable>().is_some_and(|v| v.name == var.name)
            });
            if !ok {
                report.errors.push(Issue {
                    kind: "rewritten_lookup_failed",
                    typed_path: join(&typed),
                    vcd_path: Some(join(&p)),
                    detail: "surfer-tywaves would not find a typed variable for this rewritten VCD variable".into(),
                });
            }
        }
        for (key, sub) in sorted_scopes(&scope.subscopes) {
            let sub = sub.read().unwrap();
            let mut p = path.to_vec();
            p.push(key.clone());
            walk(tyvcd, header, &sub, &p, report);
        }
    }
    for (key, root) in sorted_scopes(&tyvcd.scopes) {
        let root = root.read().unwrap();
        walk(tyvcd, &header, &root, &[key.clone()], report);
    }
    Ok(())
}

fn load_hgldd(path: &Path) -> Result<Vec<Hgldd>, String> {
    let res = if path.is_dir() {
        hgldd::reader::parse_hgldd_dir(path)
    } else {
        hgldd::reader::parse_hgldd_file(path)
    };
    res.map_err(|e| format!("cannot parse HGLDD {}: {e:?}", path.display()))
}

fn panic_msg(p: Box<dyn std::any::Any + Send>) -> String {
    if let Some(s) = p.downcast_ref::<&str>() {
        s.to_string()
    } else if let Some(s) = p.downcast_ref::<String>() {
        s.clone()
    } else {
        "unknown panic".into()
    }
}

fn default_out(vcd: &Path) -> PathBuf {
    let stem = vcd.file_stem().map(|s| s.to_string_lossy().into_owned()).unwrap_or_else(|| "wave".into());
    vcd.with_file_name(format!("{stem}.tywaves.vcd"))
}

fn print_issues(title: &str, issues: &[Issue], max: usize) {
    if issues.is_empty() {
        return;
    }
    println!("{title} ({}):", issues.len());
    for i in issues.iter().take(max) {
        match &i.vcd_path {
            Some(v) => println!("  {:<22} {}  ->  {}: {}", i.kind, i.typed_path, v, i.detail),
            None => println!("  {:<22} {}: {}", i.kind, i.typed_path, i.detail),
        }
    }
    if issues.len() > max {
        println!("  ... {} more (see --json or raise --max-report)", issues.len() - max);
    }
}

impl Args {
    fn vcd(&self) -> &Path {
        self.wave.as_deref().or(self.vcd.as_deref()).expect("clap requires a VCD")
    }
}

fn run(args: &Args) -> Result<Report, String> {
    let vcd_path = args.vcd();
    let mut report = Report {
        hgldd: args.hgldd.display().to_string(),
        vcd: vcd_path.display().to_string(),
        extra_scopes: args.extra_scopes.clone(),
        top_module: args.top_module.clone(),
        ..Default::default()
    };

    // HGLDD
    let hgldds = load_hgldd(&args.hgldd)?;
    report.counts.hgldd_objects = hgldds.iter().map(|h| h.objects.len()).sum();

    // Raw HGLDD checks that the builder would silently ignore.
    if let Some(top) = &args.top_module {
        let found = hgldds.iter().flat_map(|h| &h.objects).any(|o| {
            o.kind == ObjectKind::Module && (o.hgl_obj_name == *top || o.hdl_module_name.as_ref() == Some(top))
        });
        if !found {
            report.errors.push(Issue {
                kind: "top_module_not_found",
                typed_path: top.clone(),
                vcd_path: None,
                detail: "no HGLDD module object has this obj_name or module_name; extra scopes would be ignored".into(),
            });
        }
    }
    // Module variables and per-instance override variables (port_vars of children, recursively).
    let mut no_value: Vec<String> = Vec::new();
    fn instance_vars(prefix: &str, children: &[tywaves_rs::hgldd::spec::Instance], out: &mut Vec<String>) {
        for inst in children {
            let p = format!("{prefix}.{}", inst.name_id);
            for v in inst.port_vars.iter().flatten().filter(|v| v.value_expr.is_none()) {
                out.push(format!("{p}.{}", v.var_name));
            }
            instance_vars(&p, inst.children.as_deref().unwrap_or_default(), out);
        }
    }
    for obj in hgldds.iter().flat_map(|h| &h.objects).filter(|o| o.kind == ObjectKind::Module) {
        for v in obj.port_vars.iter().filter(|v| v.value_expr.is_none()) {
            no_value.push(format!("{}.{}", obj.hgl_obj_name, v.var_name));
        }
        instance_vars(&obj.hgl_obj_name, obj.children.as_deref().unwrap_or_default(), &mut no_value);
    }
    for typed_path in no_value {
        report.counts.dropped += 1;
        let issue = Issue {
            kind: "dropped_no_value",
            typed_path,
            vcd_path: None,
            detail: "variable has no \"value\" expression; tywaves-rs drops it silently".into(),
        };
        if args.allow_dropped {
            report.warnings.push(issue)
        } else {
            report.errors.push(issue)
        }
    }

    // TyVcd
    let mut builder = TyVcdBuilder::init(hgldds);
    if let Some(top) = &args.top_module {
        builder = builder.with_extra_artifact_scopes(args.extra_scopes.clone(), top);
    }
    match catch_unwind(AssertUnwindSafe(|| builder.build())) {
        Ok(Ok(())) => {}
        Ok(Err(e)) => return Err(format!("tywaves-rs TyVcd builder failed: {e:?}")),
        Err(p) => return Err(format!("tywaves-rs TyVcd builder panicked: {}", panic_msg(p))),
    }
    let tyvcd = builder.get_copy().ok_or("tywaves-rs builder produced no TyVcd")?;

    // VCD header
    let file = File::open(vcd_path).map_err(|e| format!("cannot open VCD {}: {e}", vcd_path.display()))?;
    let header = vcd::Parser::new(BufReader::new(file))
        .parse_header()
        .map_err(|e| format!("cannot parse VCD header {}: {e}", vcd_path.display()))?;

    // Leaf checks
    let mut checker = Checker {
        tyvcd: &tyvcd,
        header: &header,
        verbose: args.verbose && !args.quiet,
        report,
        covered: HashSet::new(),
        typed_scopes_in_vcd: Vec::new(),
    };
    if checker.verbose {
        println!("typed leaves:");
    }
    for (key, root) in sorted_scopes(&tyvcd.scopes) {
        let root = root.read().unwrap();
        checker.walk_scope(&root, &[key.clone()]);
    }
    checker.uncovered();
    let mut report = checker.report;
    if report.counts.leaves == 0 {
        report.errors.push(Issue {
            kind: "no_typed_leaves",
            typed_path: String::new(),
            vcd_path: None,
            detail: "the HGLDD produced no typed leaves; nothing was verified".into(),
        });
    }
    if args.fail_on_uncovered {
        for u in &report.uncovered {
            report.errors.push(Issue {
                kind: "uncovered",
                typed_path: u.clone(),
                vcd_path: Some(u.clone()),
                detail: "VCD variable in a typed scope is not referred to by any typed leaf".into(),
            });
        }
    }

    // Rewrite
    if !args.no_rewrite {
        let out = args.out.clone().unwrap_or_else(|| default_out(vcd_path));
        if out.extension().and_then(|e| e.to_str()) != Some("vcd") {
            return Err(format!("--out must end in .vcd: {}", out.display()));
        }
        let scopes: Vec<ScopeDef> =
            sorted_scopes(&tyvcd.scopes).into_iter().map(|(_, s)| s.read().unwrap().clone()).collect();
        let res = catch_unwind(AssertUnwindSafe(|| {
            let mut rw = VcdRewriter::new(vcd_path, scopes, out.to_string_lossy().into_owned())?;
            rw.rewrite()
        }));
        let fail = match res {
            Ok(Ok(())) => None,
            Ok(Err(e)) => Some(format!("{e:?}")),
            Err(p) => Some(format!("panic: {}", panic_msg(p))),
        };
        if let Some(detail) = fail {
            report.errors.push(Issue {
                kind: "rewrite_failed",
                typed_path: String::new(),
                vcd_path: Some(out.display().to_string()),
                detail: format!("tywaves-rs VcdRewriter failed: {detail}"),
            });
        } else {
            report.rewritten_vcd = Some(out.display().to_string());
            check_rewritten(&tyvcd, &out, &mut report)?;
        }
    }

    report.ok = report.errors.is_empty();
    Ok(report)
}

fn main() -> ExitCode {
    let args = Args::parse();
    let report = match run(&args) {
        Ok(r) => r,
        Err(e) => {
            eprintln!("spinalwaves-check: error: {e}");
            return ExitCode::from(EXIT_ERROR);
        }
    };

    if !args.quiet {
        let c = &report.counts;
        println!("spinalwaves-check");
        println!("  hgldd:   {} ({} objects)", report.hgldd, c.hgldd_objects);
        println!("  vcd:     {}", report.vcd);
        if !report.extra_scopes.is_empty() {
            println!(
                "  scopes:  --extra-scopes {} --top-module {}",
                report.extra_scopes.join(" "),
                report.top_module.as_deref().unwrap_or("")
            );
        }
        println!(
            "  typed:   {} scopes ({} missing), {} variables, {} leaves",
            c.scopes, c.scopes_missing, c.variables, c.leaves
        );
        println!(
            "  leaves:  {} resolved, {} constant, {} missing, {} width mismatch, {} unsupported, {} find_trace failures",
            c.resolved, c.constant, c.missing, c.width_mismatch, c.unsupported, c.find_trace_failed
        );
        println!("  dropped: {} vars without value; uncovered VCD vars: {}", c.dropped, c.uncovered);
        if let Some(out) = &report.rewritten_vcd {
            println!("  rewritten VCD: {out}");
        }
        print_issues("warnings", &report.warnings, args.max_report);
        if args.list_uncovered && !report.uncovered.is_empty() {
            println!("uncovered VCD variables ({}):", report.uncovered.len());
            for u in &report.uncovered {
                println!("  {u}");
            }
        }
    }
    print_issues("errors", &report.errors, args.max_report);

    if let Some(json) = &args.json {
        let text = serde_json::to_string_pretty(&report).expect("serialize report");
        if let Err(e) = std::fs::write(json, text + "\n") {
            eprintln!("spinalwaves-check: error: cannot write {}: {e}", json.display());
            return ExitCode::from(EXIT_ERROR);
        }
    }

    if report.ok {
        println!("PASS");
        ExitCode::SUCCESS
    } else {
        println!("FAIL: {} error(s)", report.errors.len());
        ExitCode::from(EXIT_FAIL)
    }
}
