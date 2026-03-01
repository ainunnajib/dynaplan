#[derive(Clone, Debug, PartialEq)]
pub enum CellValue {
    Number(f64),
    Text(String),
    Bool(bool),
}
