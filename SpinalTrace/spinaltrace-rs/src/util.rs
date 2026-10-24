use crate::graphbuilder::CriterionType;

pub fn parse_criterion(s: &str) -> Result<CriterionType, String> {
    let (kind, value) = s.split_once(':')
        .ok_or("Expected 'type:value' format")?;
    match kind.to_lowercase().as_str() {
        "statement" => Ok(CriterionType::Statement(value.into())),
        "signal" => Ok(CriterionType::Signal(value.into())),
        // SPINALTRACE: `line:<file (suffix)>:<line>` = latest activated statement on that source line.
        "line" => {
            let (file, line) = value.rsplit_once(':').ok_or("Expected 'line:<file>:<line>'")?;
            let line = line.parse::<u32>().map_err(|e| format!("Invalid line number '{}': {}", line, e))?;
            Ok(CriterionType::Line(file.into(), line))
        }
        _ => Err(format!("Unknown criterion type '{}'", kind)),
    }
}