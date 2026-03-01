use std::collections::{HashMap, HashSet};

use dynaplan_core::{
    aggregate_values, evaluate_formula as evaluate_formula_rust, spread_value, DimensionDef,
    FormulaSpec, RecalcResult, SpreadMethod, SummaryMethod,
};
use pyo3::exceptions::{PyTypeError, PyValueError};
use pyo3::prelude::*;
use pyo3::types::{PyDict, PyList};
use serde::Deserialize;
use serde_json::Value;

mod conversions;
mod model_handle;

use conversions::{
    dimension_key_from_strings, formula_value_to_pyobject, numeric_value_from_json, parse_uuid,
    py_any_to_f64, py_any_to_formula_value, recalc_result_to_pyobject,
};
pub use model_handle::ModelHandle;
use model_handle::EngineState;

#[derive(Debug, Deserialize, Default)]
struct ModelPayload {
    #[serde(default)]
    dimensions: Vec<DimensionPayload>,
    #[serde(default)]
    line_items: Vec<LineItemPayload>,
    #[serde(default)]
    dependency_edges: HashMap<String, Vec<String>>,
}

#[derive(Debug, Deserialize)]
struct DimensionPayload {
    id: String,
    #[serde(default)]
    members: Vec<String>,
}

#[derive(Debug, Deserialize)]
struct LineItemPayload {
    id: String,
    #[serde(default)]
    formula: Option<String>,
    #[serde(default)]
    references: HashMap<String, String>,
    #[serde(default)]
    cells: Vec<CellPayload>,
}

#[derive(Debug, Deserialize)]
struct CellPayload {
    dimension_key: DimensionKeyPayload,
    value: Value,
}

#[derive(Debug, Deserialize)]
#[serde(untagged)]
enum DimensionKeyPayload {
    Members(Vec<String>),
    Pipe(String),
}

impl DimensionKeyPayload {
    fn into_members(self) -> Vec<String> {
        match self {
            DimensionKeyPayload::Members(values) => values,
            DimensionKeyPayload::Pipe(value) => value
                .split('|')
                .filter(|part| !part.is_empty())
                .map(|part| part.to_string())
                .collect(),
        }
    }
}

#[pyfunction]
fn load_model(model_json: &str) -> PyResult<ModelHandle> {
    let payload: ModelPayload = serde_json::from_str(model_json).map_err(|err| {
        PyValueError::new_err(format!("Failed to deserialize model_json: {}", err))
    })?;

    let mut state = EngineState::default();
    let mut formulas: HashMap<uuid::Uuid, FormulaSpec> = HashMap::new();

    for dimension in payload.dimensions {
        let dimension_id = parse_uuid(&dimension.id, "dimension.id")?;
        let mut members = Vec::with_capacity(dimension.members.len());
        for member in &dimension.members {
            members.push(parse_uuid(member, "dimension.members[]")?);
        }
        state
            .model
            .upsert_dimension(DimensionDef::new(dimension_id, members));
    }

    for line_item in payload.line_items {
        let line_item_id = parse_uuid(&line_item.id, "line_item.id")?;
        state.graph.add_node(line_item_id);

        if let Some(expression) = line_item.formula {
            let mut references = HashMap::new();
            for (identifier, target_id) in &line_item.references {
                let reference_id = parse_uuid(target_id, "line_item.references[]")?;
                references.insert(identifier.clone(), reference_id);
                state.graph.add_dependency(line_item_id, reference_id);
            }
            formulas.insert(line_item_id, FormulaSpec::new(expression, references));
        }

        for cell in line_item.cells {
            let Some(number) = numeric_value_from_json(&cell.value) else {
                continue;
            };

            let key = dimension_key_from_strings(&cell.dimension_key.into_members())?;
            state.model.write_numeric_cell(line_item_id, key, number);
        }
    }

    for (dependent, dependencies) in payload.dependency_edges {
        let dependent_id = parse_uuid(&dependent, "dependency_edges.key")?;
        for dependency in dependencies {
            let dependency_id = parse_uuid(&dependency, "dependency_edges.value[]")?;
            state.graph.add_dependency(dependent_id, dependency_id);
        }
    }

    state.orchestrator = dynaplan_core::RecalcOrchestrator::new(formulas);
    Ok(ModelHandle::from_state(state))
}

#[pyfunction]
fn write_cell(
    py: Python<'_>,
    handle: &ModelHandle,
    line_item_id: &str,
    dimension_key: Vec<String>,
    value: &PyAny,
) -> PyResult<PyObject> {
    let line_item_uuid = parse_uuid(line_item_id, "line_item_id")?;
    let key = dimension_key_from_strings(&dimension_key)?;
    let number = py_any_to_f64(value)?;

    let mut state = handle.write()?;
    state.model.write_numeric_cell(line_item_uuid, key.clone(), number);
    state.graph.add_node(line_item_uuid);

    let orchestrator = state.orchestrator.clone();
    let graph = state.graph.clone();
    let result = orchestrator
        .recalc(&mut state.model, &graph, vec![(line_item_uuid, key)])
        .map_err(|err| PyValueError::new_err(format!("Recalculation failed: {}", err)))?;

    recalc_result_to_pyobject(py, &result)
}

#[pyfunction]
fn write_cells_bulk(py: Python<'_>, handle: &ModelHandle, cells: &PyAny) -> PyResult<PyObject> {
    let cells = cells.downcast::<PyList>().map_err(|_| {
        PyTypeError::new_err("cells must be a list of dicts with line_item_id/dimension_key/value")
    })?;

    let mut state = handle.write()?;
    let mut changed = Vec::with_capacity(cells.len());

    for entry in cells.iter() {
        let row = entry.downcast::<PyDict>().map_err(|_| {
            PyTypeError::new_err("Each cell entry must be a dict")
        })?;

        let line_item_id_any = row
            .get_item("line_item_id")
            .ok_or_else(|| PyValueError::new_err("Missing line_item_id in bulk row"))?;
        let line_item_id = line_item_id_any.extract::<String>()?;
        let line_item_uuid = parse_uuid(&line_item_id, "line_item_id")?;

        let dimension_key_any = row
            .get_item("dimension_key")
            .or_else(|| row.get_item("dimension_members"))
            .ok_or_else(|| {
                PyValueError::new_err("Missing dimension_key (or dimension_members) in bulk row")
            })?;

        let dimension_parts = if let Ok(parts) = dimension_key_any.extract::<Vec<String>>() {
            parts
        } else if let Ok(pipe) = dimension_key_any.extract::<String>() {
            pipe.split('|')
                .filter(|part| !part.is_empty())
                .map(|part| part.to_string())
                .collect::<Vec<String>>()
        } else {
            return Err(PyTypeError::new_err(
                "dimension_key must be a list[str] or pipe-delimited string",
            ));
        };

        let value_any = row
            .get_item("value")
            .ok_or_else(|| PyValueError::new_err("Missing value in bulk row"))?;
        let number = py_any_to_f64(value_any)?;
        let key = dimension_key_from_strings(&dimension_parts)?;

        state.model.write_numeric_cell(line_item_uuid, key.clone(), number);
        state.graph.add_node(line_item_uuid);
        changed.push((line_item_uuid, key));
    }

    let orchestrator = state.orchestrator.clone();
    let graph = state.graph.clone();
    let result = if changed.is_empty() {
        RecalcResult::default()
    } else {
        orchestrator
            .recalc(&mut state.model, &graph, changed)
            .map_err(|err| PyValueError::new_err(format!("Recalculation failed: {}", err)))?
    };

    recalc_result_to_pyobject(py, &result)
}

#[pyfunction]
fn read_cell(
    py: Python<'_>,
    handle: &ModelHandle,
    line_item_id: &str,
    dimension_key: Vec<String>,
) -> PyResult<PyObject> {
    let line_item_uuid = parse_uuid(line_item_id, "line_item_id")?;
    let key = dimension_key_from_strings(&dimension_key)?;
    let state = handle.read()?;
    Ok(match state.model.read_numeric_cell(&line_item_uuid, &key) {
        Some(value) => value.into_py(py),
        None => py.None(),
    })
}

#[pyfunction]
fn read_cells(
    py: Python<'_>,
    handle: &ModelHandle,
    line_item_id: &str,
    filters: Option<&PyDict>,
) -> PyResult<Vec<PyObject>> {
    let line_item_uuid = parse_uuid(line_item_id, "line_item_id")?;
    let state = handle.read()?;
    let block = match state.model.block(&line_item_uuid) {
        Some(block) => block,
        None => return Ok(Vec::new()),
    };

    let mut allowed_groups: Vec<HashSet<uuid::Uuid>> = Vec::new();
    if let Some(filters) = filters {
        for (_, value) in filters.iter() {
            let members = value.extract::<Vec<String>>()?;
            let mut allowed = HashSet::with_capacity(members.len());
            for member in members {
                allowed.insert(parse_uuid(&member, "filters[]")?);
            }
            if !allowed.is_empty() {
                allowed_groups.push(allowed);
            }
        }
    }

    let mut out = Vec::new();
    for (key, value) in block.iter_columnar() {
        let matches = allowed_groups.iter().all(|allowed| {
            key.members()
                .iter()
                .any(|member| allowed.contains(member))
        });
        if matches {
            out.push((*value).into_py(py));
        }
    }

    Ok(out)
}

#[pyfunction]
fn evaluate_formula(
    py: Python<'_>,
    text: &str,
    context: Option<&PyDict>,
) -> PyResult<PyObject> {
    let mut converted = HashMap::new();
    if let Some(mapping) = context {
        for (key, value) in mapping.iter() {
            converted.insert(
                key.str()?.to_str()?.to_string(),
                py_any_to_formula_value(value)?,
            );
        }
    }

    let result = evaluate_formula_rust(text, converted)
        .map_err(|err| PyValueError::new_err(format!("Formula evaluation failed: {}", err)))?;
    formula_value_to_pyobject(py, result)
}

#[pyfunction]
fn get_recalc_order(handle: &ModelHandle, changed: Vec<String>) -> PyResult<Vec<String>> {
    let mut changed_ids = HashSet::new();
    for value in changed {
        changed_ids.insert(parse_uuid(&value, "changed[]")?);
    }

    let state = handle.read()?;
    let order = state
        .graph
        .get_recalc_order(changed_ids)
        .map_err(|err| PyValueError::new_err(format!("Graph error: {}", err)))?;
    Ok(order.into_iter().map(|id| id.to_string()).collect::<Vec<String>>())
}

#[pyfunction]
fn spread_top_down(
    handle: &ModelHandle,
    total: f64,
    member_count: usize,
    method: &str,
    weights: Option<Vec<f64>>,
    existing_values: Option<Vec<f64>>,
) -> PyResult<Vec<f64>> {
    let _ = handle;
    let parsed_method = SpreadMethod::parse(method)
        .map_err(|err| PyValueError::new_err(format!("Invalid spread method: {}", err)))?;
    spread_value(
        total,
        member_count,
        parsed_method,
        weights.as_deref(),
        existing_values.as_deref(),
    )
    .map_err(|err| PyValueError::new_err(format!("Spread calculation failed: {}", err)))
}

#[pyfunction]
fn aggregate_bottom_up(
    handle: &ModelHandle,
    values: Vec<f64>,
    method: &str,
) -> PyResult<f64> {
    let _ = handle;
    let parsed_method = SummaryMethod::parse(method)
        .map_err(|err| PyValueError::new_err(format!("Invalid summary method: {}", err)))?;
    Ok(aggregate_values(&values, parsed_method))
}

#[pymodule]
fn dynaplan_engine(_py: Python<'_>, module: &PyModule) -> PyResult<()> {
    module.add_class::<ModelHandle>()?;
    module.add_function(wrap_pyfunction!(load_model, module)?)?;
    module.add_function(wrap_pyfunction!(write_cell, module)?)?;
    module.add_function(wrap_pyfunction!(write_cells_bulk, module)?)?;
    module.add_function(wrap_pyfunction!(read_cell, module)?)?;
    module.add_function(wrap_pyfunction!(read_cells, module)?)?;
    module.add_function(wrap_pyfunction!(evaluate_formula, module)?)?;
    module.add_function(wrap_pyfunction!(get_recalc_order, module)?)?;
    module.add_function(wrap_pyfunction!(spread_top_down, module)?)?;
    module.add_function(wrap_pyfunction!(aggregate_bottom_up, module)?)?;
    Ok(())
}
