use std::collections::{HashMap, HashSet};
use std::error::Error;
use std::fmt;

use uuid::Uuid;

use crate::block::CalculationBlock;
use crate::calc::context::{build_cell_context, collect_recalc_keys, FormulaSpec};
use crate::calc::parallel::{build_topological_levels, execute_level_parallel};
use crate::dimension::DimensionKey;
use crate::formula::{get_references, parse_formula, ASTNode, Evaluator, FormulaValue};
use crate::graph::{DependencyGraph, GraphError};
use crate::model::ModelState;
use crate::value::CellValue;

#[derive(Clone, Debug)]
pub enum CalcError {
    Graph(GraphError),
    Formula {
        line_item_id: Uuid,
        message: String,
    },
    MissingReferenceBinding {
        line_item_id: Uuid,
        identifier: String,
    },
    NonNumericResult {
        line_item_id: Uuid,
        key: DimensionKey,
        value: CellValue,
    },
}

impl fmt::Display for CalcError {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            CalcError::Graph(err) => write!(f, "Graph error: {}", err),
            CalcError::Formula {
                line_item_id,
                message,
            } => write!(
                f,
                "Formula evaluation error for line item {}: {}",
                line_item_id, message
            ),
            CalcError::MissingReferenceBinding {
                line_item_id,
                identifier,
            } => write!(
                f,
                "Formula for line item {} references {:?} but no binding exists",
                line_item_id, identifier
            ),
            CalcError::NonNumericResult {
                line_item_id,
                key,
                value,
            } => write!(
                f,
                "Formula for line item {} produced non-numeric value {:?} for key {:?}",
                line_item_id, value, key
            ),
        }
    }
}

impl Error for CalcError {}

#[derive(Clone, Debug, Default)]
pub struct RecalcResult {
    pub ordered_nodes: Vec<Uuid>,
    pub levels: Vec<Vec<Uuid>>,
    pub recalculated_line_items: usize,
    pub recalculated_cells: usize,
}

#[derive(Clone, Debug, Default)]
pub struct RecalcOrchestrator {
    formulas: HashMap<Uuid, FormulaSpec>,
}

#[derive(Clone, Debug)]
struct CompiledFormula {
    ast: ASTNode,
    spec: FormulaSpec,
}

#[derive(Clone, Debug)]
struct BlockUpdate {
    line_item_id: Uuid,
    cells: Vec<(DimensionKey, f64)>,
}

impl RecalcOrchestrator {
    pub fn new(formulas: HashMap<Uuid, FormulaSpec>) -> Self {
        Self { formulas }
    }

    pub fn formulas(&self) -> &HashMap<Uuid, FormulaSpec> {
        &self.formulas
    }

    pub fn upsert_formula(&mut self, line_item_id: Uuid, formula: FormulaSpec) {
        self.formulas.insert(line_item_id, formula);
    }

    pub fn remove_formula(&mut self, line_item_id: &Uuid) {
        self.formulas.remove(line_item_id);
    }

    pub fn recalc(
        &self,
        model: &mut ModelState,
        graph: &DependencyGraph,
        changed_cells: Vec<(Uuid, DimensionKey)>,
    ) -> Result<RecalcResult, CalcError> {
        let changed_nodes = changed_cells
            .into_iter()
            .map(|(line_item_id, _)| line_item_id)
            .collect::<HashSet<Uuid>>();

        if changed_nodes.is_empty() {
            return Ok(RecalcResult::default());
        }

        let ordered_nodes = graph.get_recalc_order(changed_nodes).map_err(CalcError::Graph)?;
        if ordered_nodes.is_empty() {
            return Ok(RecalcResult {
                ordered_nodes,
                levels: Vec::new(),
                recalculated_line_items: 0,
                recalculated_cells: 0,
            });
        }

        let levels = build_topological_levels(graph, &ordered_nodes);
        let compiled_formulas = self.compile_formulas()?;
        let mut recalculated_line_items = HashSet::new();
        let mut recalculated_cells = 0usize;

        for level in &levels {
            let snapshot = model.blocks().clone();
            let updates = execute_level_parallel(level, |line_item_id| {
                recalc_block(line_item_id, &compiled_formulas, &snapshot)
            })?;

            for block_update in updates.into_iter().flatten() {
                if block_update.cells.is_empty() {
                    continue;
                }

                recalculated_line_items.insert(block_update.line_item_id);
                recalculated_cells += block_update.cells.len();

                for (key, value) in block_update.cells {
                    model.write_numeric_cell(block_update.line_item_id, key, value);
                }
            }
        }

        Ok(RecalcResult {
            ordered_nodes,
            levels,
            recalculated_line_items: recalculated_line_items.len(),
            recalculated_cells,
        })
    }

    fn compile_formulas(&self) -> Result<HashMap<Uuid, CompiledFormula>, CalcError> {
        let mut compiled = HashMap::with_capacity(self.formulas.len());

        for (line_item_id, formula_spec) in &self.formulas {
            let ast = parse_formula(formula_spec.expression()).map_err(|err| CalcError::Formula {
                line_item_id: *line_item_id,
                message: err.to_string(),
            })?;

            let mut referenced_identifiers = get_references(formula_spec.expression())
                .into_iter()
                .collect::<Vec<String>>();
            referenced_identifiers.sort_unstable();

            for identifier in referenced_identifiers {
                if !formula_spec.references().contains_key(&identifier) {
                    return Err(CalcError::MissingReferenceBinding {
                        line_item_id: *line_item_id,
                        identifier,
                    });
                }
            }

            compiled.insert(
                *line_item_id,
                CompiledFormula {
                    ast,
                    spec: formula_spec.clone(),
                },
            );
        }

        Ok(compiled)
    }
}

fn recalc_block(
    line_item_id: Uuid,
    formulas: &HashMap<Uuid, CompiledFormula>,
    snapshot: &HashMap<Uuid, CalculationBlock>,
) -> Result<Option<BlockUpdate>, CalcError> {
    let Some(formula) = formulas.get(&line_item_id) else {
        return Ok(None);
    };

    let mut updates = Vec::new();
    let recalc_keys = collect_recalc_keys(&line_item_id, &formula.spec, snapshot);

    for key in recalc_keys {
        let context = build_cell_context(&formula.spec, &key, snapshot);
        let value = evaluate_ast_cell_context(&formula.ast, context).map_err(|message| {
            CalcError::Formula {
                line_item_id,
                message,
            }
        })?;

        match value {
            CellValue::Number(number) => updates.push((key, number)),
            other => {
                return Err(CalcError::NonNumericResult {
                    line_item_id,
                    key,
                    value: other,
                })
            }
        }
    }

    Ok(Some(BlockUpdate {
        line_item_id,
        cells: updates,
    }))
}

fn evaluate_ast_cell_context(
    ast: &ASTNode,
    context: HashMap<String, CellValue>,
) -> Result<CellValue, String> {
    let converted_context = context
        .into_iter()
        .map(|(identifier, value)| (identifier, FormulaValue::from(value)))
        .collect::<HashMap<String, FormulaValue>>();

    let evaluator = Evaluator::new(converted_context);
    let result = evaluator.evaluate(ast).map_err(|err| err.to_string())?;
    CellValue::try_from(result).map_err(|err| err.to_string())
}
