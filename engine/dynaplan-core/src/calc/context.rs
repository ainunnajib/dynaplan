use std::cmp::Ordering;
use std::collections::{HashMap, HashSet};
use std::error::Error;
use std::fmt;

use uuid::Uuid;

use crate::block::CalculationBlock;
use crate::dimension::DimensionKey;
use crate::formula::get_references;
use crate::value::CellValue;

#[derive(Clone, Debug, PartialEq, Eq)]
pub enum ContextError {
    MissingReferenceBinding { identifier: String },
}

impl fmt::Display for ContextError {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            ContextError::MissingReferenceBinding { identifier } => {
                write!(f, "Missing reference binding for identifier {:?}", identifier)
            }
        }
    }
}

impl Error for ContextError {}

#[derive(Clone, Debug, Default, PartialEq, Eq)]
pub struct FormulaSpec {
    expression: String,
    references: HashMap<String, Uuid>,
}

impl FormulaSpec {
    pub fn new(expression: impl Into<String>, references: HashMap<String, Uuid>) -> Self {
        Self {
            expression: expression.into(),
            references,
        }
    }

    pub fn inferred(
        expression: impl Into<String>,
        reference_lookup: &HashMap<String, Uuid>,
    ) -> Result<Self, ContextError> {
        let expression = expression.into();
        let mut references = HashMap::new();
        let mut identifiers = get_references(&expression).into_iter().collect::<Vec<String>>();
        identifiers.sort_unstable();

        for identifier in identifiers {
            let line_item_id = reference_lookup
                .get(&identifier)
                .copied()
                .ok_or_else(|| ContextError::MissingReferenceBinding {
                    identifier: identifier.clone(),
                })?;
            references.insert(identifier, line_item_id);
        }

        Ok(Self::new(expression, references))
    }

    pub fn expression(&self) -> &str {
        &self.expression
    }

    pub fn references(&self) -> &HashMap<String, Uuid> {
        &self.references
    }
}

pub fn collect_recalc_keys(
    line_item_id: &Uuid,
    formula: &FormulaSpec,
    blocks: &HashMap<Uuid, CalculationBlock>,
) -> Vec<DimensionKey> {
    let mut keys = HashSet::new();

    if let Some(block) = blocks.get(line_item_id) {
        for key in block.key_column() {
            keys.insert(key.clone());
        }
    }

    for dependency_id in formula.references().values() {
        if let Some(block) = blocks.get(dependency_id) {
            for key in block.key_column() {
                keys.insert(key.clone());
            }
        }
    }

    let mut ordered = keys.into_iter().collect::<Vec<DimensionKey>>();
    ordered.sort_unstable_by(compare_dimension_key);
    ordered
}

pub fn build_cell_context(
    formula: &FormulaSpec,
    key: &DimensionKey,
    blocks: &HashMap<Uuid, CalculationBlock>,
) -> HashMap<String, CellValue> {
    let mut context = HashMap::new();

    for (identifier, line_item_id) in formula.references() {
        let value = blocks
            .get(line_item_id)
            .and_then(|block| block.read_numeric(key))
            .unwrap_or(0.0);
        context.insert(identifier.clone(), CellValue::Number(value));
    }

    context
}

fn compare_dimension_key(left: &DimensionKey, right: &DimensionKey) -> Ordering {
    left.members()
        .iter()
        .map(|member| member.as_u128())
        .cmp(right.members().iter().map(|member| member.as_u128()))
}
