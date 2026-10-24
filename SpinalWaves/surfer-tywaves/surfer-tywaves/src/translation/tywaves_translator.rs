use std::path::Path;
use std::sync::mpsc::Sender;
use std::sync::{Arc, RwLock};

use camino::Utf8Path;

use crate::message::Message;
use crate::translation::{Translator, ValueKind, ValueRepr};
use crate::wasm_util::perform_work;
use surfer_translation_types::{BasicTranslator, VariableValue, SubFieldTranslationResult};
use crate::wave_container::{ScopeId, VarId, VariableMeta};
use crate::UnsignedTranslator;

use super::{TranslationPreference, TranslationResult, VariableInfo};

use color_eyre::{eyre::eyre, Result}; // Add this line

// Tywaves-rs
use tywaves_rs::tyvcd::builder::GenericBuilder;
use tywaves_rs::tyvcd::trace_pointer::TraceFinder;
use tywaves_rs::{hgldd, tyvcd::builder as tybuilder, tyvcd::spec as tyvcd};

type PrefTypeTranslator = UnsignedTranslator;
static PREFERRED_TRANSLATOR: PrefTypeTranslator = PrefTypeTranslator {};

/// Internal state of the [TywavesTranslator]
struct TywaveState {
    builder: tybuilder::TyVcdBuilder<hgldd::spec::Hgldd>,
}
impl TywaveState {
    // Internal function to get the tyvcd state
    fn tyvcd(&self) -> &tyvcd::TyVcd {
        // SAFETY: The builder is guaranteed to be initialized at this point
        self.builder.get_ref().unwrap()
    }
}

#[inline]
fn create_translation_result_name(variable: &tyvcd::Variable) -> String {
    // format!(
    //     "{:?}\n{}: {}",
    //     variable.get_trace_value(),
    //     variable.high_level_info.type_name,
    //     variable.name
    // )
    format!("{}: {}", variable.high_level_info.type_name, variable.name)
}
/// TywavesTranslator
pub struct TywavesTranslator {
    // dyn Translator
    inner_translator: Box<dyn BasicTranslator<VarId, ScopeId>>,
    state: TywaveState,
    top_module_name: String,
}

impl TywavesTranslator {
    /// Create a new TywavesTranslator.
    ///
    /// It parses an hgldd directory and initialize the translator by building the [tyvcd::TyVcd] IR internally.
    ///
    /// It optionally adds `extra_scopes` at the top level of the hierarchy. If this is not wanted:
    /// pass an empty `extra_scopes` vector if you don't want to add any extra scopes.
    ///
    /// ```no_run
    /// use camino::Utf8Path;
    /// use std::path::Path;
    /// use tywaves_rs::translation::TywavesTranslator;
    ///
    /// let hgldd_dir = Utf8Path::new("path/to/hgldd");
    /// let top_module_name = "top_module".to_string();
    ///
    /// let translator = TywavesTranslator::new(&hgldd_dir, Vec::new(), &top_module_name).unwrap();
    /// ```
    ///
    /// Returns an error if the [tyvcd::TyVcd] cannot be built.
    pub fn new(
        hgldd_dir: &Utf8Path,
        extra_scopes: Vec<String>,
        top_module_name: &String,
        inner_translator: Box<dyn BasicTranslator<VarId, ScopeId>>,
    ) -> Result<Self> {
        // Parse the hgldd directory and initialize the builder and state
        let hgldd = hgldd::reader::parse_hgldd_dir(hgldd_dir.as_ref()).map_err(|e| {
            eyre!(
                "Failed to parse the hgldd directory: {:?}.\nError: {:?}",
                hgldd_dir,
                e
            )
        })?;
        let mut state = TywaveState {
            builder: tybuilder::TyVcdBuilder::init(hgldd)
                .with_extra_artifact_scopes(extra_scopes, top_module_name),
        };
        // Build the tyvcd state
        let res_build = state.builder.build();
        match res_build {
            Ok(_) => Ok(()),
            Err(e) => match e {
                tybuilder::BuilderError::MissingTraceValue(_) => Ok(()),
                tybuilder::BuilderError::MissingTraceValueRequired(_)
                | tybuilder::BuilderError::FailedToBuildVariable(_)
                | tybuilder::BuilderError::GenericFailure(_) => Err(eyre!(
                    "Failed to build the Tywaves state from the hgldd directory.\nError: {:?}",
                    e
                )),
            },
        }?;

        Ok(TywavesTranslator {
            state,
            inner_translator,
            top_module_name: top_module_name.to_string(),
        })
    }

    /// Rewrite the vcd file according to the tywaves internal state
    pub fn vcd_rewrite(&self, vcd_path: &Path) -> Result<String> {
        let tywaves_scopes = &self.state.tyvcd().scopes;
        // Get the list of scopes
        let scopes_def_list = tywaves_scopes
            .into_iter()
            .map(|(_, v)| (v.read().unwrap().clone()))
            .collect();

        let mut vcd_rewriter = tywaves_rs::vcd_rewrite::VcdRewriter::new(
            vcd_path,
            scopes_def_list,
            format!("{}.vcd", self.top_module_name),
        )
        .map_err(|e| eyre!("Failed to rewrite the vcd file.\nError: {:?}", e))?;
        vcd_rewriter
            .rewrite()
            .map_err(|e| eyre!("Failed to rewrite the vcd file.\nError: {:?}", e))?;
        Ok(vcd_rewriter.get_final_file().clone())
    }

    /// Load the TywavesTranslator from an input hgldd directory (optionally
    /// adding `extra_scopes` at the top level of the hierarchy).
    ///
    /// Pass empty `extra_scopes` if you don't want to add any extra scopes.
    pub fn load(
        hgldd_dir_path: &Utf8Path,
        sender: Sender<Message>,
        extra_scopes: Vec<String>,
        top_module_name: String,
        inner_translator: Box<dyn BasicTranslator<VarId, ScopeId>>,
    ) {
        let hgldd_dir_path = hgldd_dir_path.to_owned();

        // Create a new thread to load the translator
        perform_work(move || {
            match TywavesTranslator::new(
                &hgldd_dir_path,
                extra_scopes,
                &top_module_name,
                inner_translator,
            ) {
                Ok(translator) => sender
                    .send(Message::TranslatorLoaded(Box::new(translator)))
                    .unwrap(),
                Err(e) => sender.send(Message::Error(e)).unwrap(),
            }
        });
    }

    /// Given a variable meta, this explores the state and finds the variable.
    /// Internal usage only.
    fn find_variable(&self, variable: &VariableMeta) -> Result<Arc<RwLock<tyvcd::Variable>>> {
        let var = &variable.var;

        // A workaround. Upstream Surfer removed var.full_path(), so this does the work of the old method.
        let var_full_path = var.path
            .strs
            .iter()
            .cloned()
            .chain([var.name.clone()])
            .collect::<Vec<String>>();
    
        // let var_full_path = variable.var.full_path();

        // Query the state for the trace of the variable. Find the trace by using the full path of the variable
        let trace_getter = self
            .state
            .tyvcd()
            .find_trace(&var_full_path)
            .ok_or_else(|| eyre!("Variable not found in the state: {:?}", var_full_path))?;

        // Try to cast the variable to tyvcd::Variable
        let binding = trace_getter.read().unwrap();
        let var = binding
            .as_any()
            .downcast_ref::<tyvcd::Variable>()
            .ok_or_else(|| eyre!("Failed to downcast {:?} to tyvcd::Variable", var_full_path))?;

        Ok(Arc::new(RwLock::new(var.clone())))
    }

    /// Extract the value of a subfield from a raw value.
    /// Return the value of the subfield and the rest of the raw value.
    fn get_sub_raw_val<'a>(
        &self,
        subfield_kind: &tyvcd::VariableKind,
        raw_val_vcd: &'a str,
    ) -> (&'a str, &'a str) {
        // Get size of real type
        let size = subfield_kind.find_width() as usize;
        if raw_val_vcd.len() < size {
            return ("0", raw_val_vcd);
        }
        // Return the value of the subfield and the rest of the raw value
        (&raw_val_vcd[..size], &raw_val_vcd[size..])
    }

    /// Translate a [tyvcd::Variable] into a [TranslationResult].
    fn translate_variable(
        &self,
        variable: &tyvcd::Variable,
        raw_val_vcd: &str,
    ) -> Result<TranslationResult> {
        // Create the value representation
        let render_fn = |num_bits: u64, raw_val_vcd: &str| {
            self.inner_translator
                .basic_translate(num_bits, &VariableValue::String(raw_val_vcd.to_string()))
                .0
        };

        let val_repr_str = variable.create_val_repr(raw_val_vcd, &render_fn);
        // let val_repr = ValueRepr::String(format!(
        //     "{} {}",
        //     variable.high_level_info.type_name, val_repr_str
        // ));
        let val_repr = ValueRepr::String(val_repr_str);

        // Create a result based on the kind of the variable
        let result = match &variable.kind {
            // Create a bool if the variable is a ground with width 1
            // otherwise a bit vector
            tyvcd::VariableKind::Ground(width) => {
                let mut subfields = vec![];
                for i in 0..*width as usize {
                    let subfield = TranslationResult {
                        val: ValueRepr::String(raw_val_vcd.chars().nth(i).unwrap().to_string()),
                        subfields: vec![],
                        kind: ValueKind::Normal,
                    };
                    subfields.push(SubFieldTranslationResult::new(
                        i.to_string(),
                        subfield,
                    ));
                }

                let subfields = match self.convert_kind2info(&variable.kind) {
                    VariableInfo::Bool => vec![],
                    _ => subfields,
                };

                // let kind = if subfields.len() > 1 {
                //     ValueKind::Custom(Color32::KHAKI)
                // } else {
                //     ValueKind::Normal
                // }; // TODO!: change this to use the correct value
                let kind = ValueKind::Normal;

                TranslationResult {
                    val: val_repr,
                    subfields,
                    kind,
                }
            }
            // Create a compound value if the variable is a struct or a vector
            tyvcd::VariableKind::Struct { fields } | tyvcd::VariableKind::Vector { fields } => {
                // Collect the subfields of the bundle
                let mut subfields = vec![];

                let mut _raw_val_vcd = raw_val_vcd;
                let mut _val = "0";
                for field in fields {
                    // Get the value of the subfield
                    (_val, _raw_val_vcd) = self.get_sub_raw_val(&field.kind, _raw_val_vcd);

                    subfields.push(SubFieldTranslationResult::new(
                        create_translation_result_name(field),
                        self.translate_variable(field, _val)?,
                    ));
                }

                TranslationResult {
                    val: val_repr,
                    subfields,
                    // kind: ValueKind::Custom(Color32::BLUE),
                    kind: ValueKind::Normal,
                }
            }
            _ => TranslationResult {
                val: ValueRepr::String(raw_val_vcd.to_string()),
                subfields: vec![],
                kind: ValueKind::Undef,
            },
        };

        Ok(result)
    }

    // TODO: implement the conversion from tywaves types to VariableInfo
    fn convert_kind2info(&self, real_type: &tyvcd::VariableKind) -> VariableInfo {
        match real_type {
            tyvcd::VariableKind::Ground(width) => {
                if *width == 1 && self.inner_translator.name() == PREFERRED_TRANSLATOR.name() {
                    VariableInfo::Bool
                } else {
                    // TODO: Change this to bits
                    let mut subfields = vec![];
                    for i in 0..*width {
                        subfields.push((i.to_string(), VariableInfo::Bool));
                    }
                    VariableInfo::Compound { subfields }
                }
            }
            tyvcd::VariableKind::Struct { fields } | tyvcd::VariableKind::Vector { fields } => {
                VariableInfo::Compound {
                    // TODO: Fix this
                    subfields: fields
                        .iter()
                        .map(|f| {
                            (
                                create_translation_result_name(f),
                                self.convert_kind2info(&f.kind),
                            )
                        })
                        .collect(),
                }
            }
            _ => VariableInfo::String,
        }
    }
}

impl Translator<VarId, ScopeId, Message> for TywavesTranslator {
    fn name(&self) -> String {
        format!("Tywaves {}", self.inner_translator.name())
    }

    fn translate(
        &self,
        variable: &VariableMeta,
        value: &VariableValue,
    ) -> Result<TranslationResult> {
        let var = self.find_variable(variable)?;
        let var = var.read().unwrap();

        // Extract the raw value from the vcd in binary format
        let raw_val_vcd = match value {
            VariableValue::BigUint(v) => format!("{v:0b}"),
            VariableValue::String(v) => v.clone(),
        };

        // Add extra bits
        let raw_val_vcd = format!(
            "{:0>width$}",
            raw_val_vcd,
            width = var.kind.find_width() as usize
        );

        self.translate_variable(&var, &raw_val_vcd)
    }

    // Get the variable info from the kind of the variable
    fn variable_info(&self, variable: &VariableMeta) -> Result<VariableInfo> {
        let var = self.find_variable(variable)?;
        let kind = &var.read().unwrap().kind;

        // Convert parent var to VariableInfo
        Ok(self.convert_kind2info(kind))
    }

    // Tell if the variable can be translated or not
    fn translates(&self, variable: &VariableMeta) -> Result<TranslationPreference> {
        if let Some(b) = variable.num_bits {
            if b == 1 {
                return Ok(TranslationPreference::Yes);
            }
        }
        if self.inner_translator.name() == PREFERRED_TRANSLATOR.name() {
            // Prefer to translate with BitTranslator as inner translator
            Ok(TranslationPreference::Prefer)
        } else if self.find_variable(variable).is_ok() {
            // Get the type of the selected variable
            Ok(TranslationPreference::Yes)
        } else {
            Ok(TranslationPreference::No)
        }
    }

    fn reload(&self, _sender: Sender<Message>) {
        // TODO: Implement reload for tywaves translator
    }
}
