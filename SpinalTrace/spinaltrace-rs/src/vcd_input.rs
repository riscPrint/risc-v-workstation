//! Accept digital SystemVerilog declarations emitted by fst2vcd.
use std::{fs::File, io::{self, BufRead, BufReader, Cursor, Read}, path::Path};

pub(crate) struct DigitalTypes<R> {
    inner: R,
    pending: Cursor<Vec<u8>>,
    header: bool,
}

impl<R: BufRead> DigitalTypes<R> {
    fn new(inner: R) -> Self {
        Self { inner, pending: Cursor::new(Vec::new()), header: true }
    }
}

impl<R: BufRead> Read for DigitalTypes<R> {
    fn read(&mut self, output: &mut [u8]) -> io::Result<usize> {
        if output.is_empty() { return Ok(0); }
        let n = self.pending.read(output)?;
        if n != 0 { return Ok(n); }
        if !self.header { return self.inner.read(output); }
        let mut line = String::new();
        if self.inner.read_line(&mut line)? == 0 { return Ok(0); }
        let words: Vec<_> = line.split_whitespace().collect();
        if words.first() == Some(&"$enddefinitions") { self.header = false; }
        if words.first() == Some(&"$var") && matches!(words.get(1), Some(&"logic") | Some(&"bit")) {
            // Both are digital bit vectors. Keep width, identifier, name and range.
            line = format!("$var wire {}\n", words[2..].join(" "));
        }
        self.pending = Cursor::new(line.into_bytes());
        self.pending.read(output)
    }
}

pub(crate) type Parser = vcd::Parser<BufReader<DigitalTypes<BufReader<File>>>>;
pub(crate) fn open(path: impl AsRef<Path>) -> io::Result<Parser> {
    Ok(vcd::Parser::new(BufReader::new(DigitalTypes::new(BufReader::new(File::open(path)?)))))
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn fst_digital_types_keep_four_state_values() {
        let input = b"$scope module Top $end\n$var logic 1 ! flag $end\n$var bit 2 # data [1:0] $end\n$upscope $end\n$enddefinitions $end\n#0\nx!\nb1z #\n";
        let mut parser = vcd::Parser::new(BufReader::new(DigitalTypes::new(Cursor::new(input))));
        let header = parser.parse_header().unwrap();
        assert_eq!(header.find_var(&["Top", "data"]).unwrap().size, 2);
        let commands: Vec<_> = parser.map(Result::unwrap).collect();
        assert_eq!(commands.len(), 3);
        assert!(matches!(commands[1], vcd::Command::ChangeScalar(_, vcd::Value::X)));
    }
}
