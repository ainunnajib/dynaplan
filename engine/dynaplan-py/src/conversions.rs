use dynaplan_core::{CellValue, DimensionKey, FormulaValue, RecalcResult};
use pyo3::exceptions::{PyTypeError, PyValueError};
use pyo3::prelude::*;
use pyo3::types::{PyBool, PyDict, PyFloat, PyInt, PyList, PyString, PyTuple};
use serde_json::Value;
use uuid::Uuid;

pub fn parse_uuid(value: &str, field: &str) -> PyResult<Uuid> {
    Uuid::parse_str(value).map_err(|err| {
        PyValueError::new_err(format!(
            "Invalid UUID for {}: {} ({})",
            field, value, err
        ))
    })
}

pub fn dimension_key_from_strings(parts: &[String]) -> PyResult<DimensionKey> {
    let mut members = Vec::with_capacity(parts.len());
    for (index, part) in parts.iter().enumerate() {
        members.push(parse_uuid(part, &format!("dimension_key[{}]", index))?);
    }
    Ok(DimensionKey::new(members))
}

pub fn numeric_value_from_json(value: &Value) -> Option<f64> {
    match value {
        Value::Number(number) => number.as_f64(),
        Value::Bool(v) => Some(if *v { 1.0 } else { 0.0 }),
        Value::String(text) => text.parse::<f64>().ok(),
        _ => None,
    }
}

pub fn py_any_to_f64(value: &PyAny) -> PyResult<f64> {
    if value.is_instance_of::<PyBool>()? {
        let v = value.extract::<bool>()?;
        return Ok(if v { 1.0 } else { 0.0 });
    }

    if value.is_instance_of::<PyFloat>()? || value.is_instance_of::<PyInt>()? {
        return value.extract::<f64>();
    }

    if value.is_instance_of::<PyString>()? {
        let text = value.extract::<String>()?;
        return text.parse::<f64>().map_err(|_| {
            PyTypeError::new_err(format!("Value {:?} cannot be converted to f64", text))
        });
    }

    Err(PyTypeError::new_err(
        "Expected a numeric/boolean/string-coercible value",
    ))
}

pub fn py_any_to_formula_value(value: &PyAny) -> PyResult<FormulaValue> {
    if value.is_none() {
        return Ok(FormulaValue::Null);
    }

    if value.is_instance_of::<PyBool>()? {
        return Ok(FormulaValue::Bool(value.extract::<bool>()?));
    }

    if value.is_instance_of::<PyFloat>()? || value.is_instance_of::<PyInt>()? {
        return Ok(FormulaValue::Number(value.extract::<f64>()?));
    }

    if value.is_instance_of::<PyString>()? {
        return Ok(FormulaValue::Text(value.extract::<String>()?));
    }

    if let Ok(items) = value.downcast::<PyList>() {
        let mut converted = Vec::with_capacity(items.len());
        for item in items.iter() {
            converted.push(py_any_to_formula_value(item)?);
        }
        return Ok(FormulaValue::List(converted));
    }

    if let Ok(items) = value.downcast::<PyTuple>() {
        let mut converted = Vec::with_capacity(items.len());
        for item in items.iter() {
            converted.push(py_any_to_formula_value(item)?);
        }
        return Ok(FormulaValue::List(converted));
    }

    if let Ok(mapping) = value.downcast::<PyDict>() {
        let mut converted = std::collections::HashMap::with_capacity(mapping.len());
        for (key, item) in mapping.iter() {
            converted.insert(key.str()?.to_str()?.to_string(), py_any_to_formula_value(item)?);
        }
        return Ok(FormulaValue::Map(converted));
    }

    Err(PyTypeError::new_err(
        "Unsupported context value type for formula evaluation",
    ))
}

pub fn formula_value_to_pyobject(py: Python<'_>, value: FormulaValue) -> PyResult<PyObject> {
    match value {
        FormulaValue::Number(v) => Ok(v.into_py(py)),
        FormulaValue::Text(v) => Ok(v.into_py(py)),
        FormulaValue::Bool(v) => Ok(v.into_py(py)),
        FormulaValue::Null => Ok(py.None()),
        FormulaValue::List(values) => {
            let mut converted = Vec::with_capacity(values.len());
            for item in values {
                converted.push(formula_value_to_pyobject(py, item)?);
            }
            Ok(converted.into_py(py))
        }
        FormulaValue::Map(values) => {
            let out = PyDict::new(py);
            for (key, item) in values {
                out.set_item(key, formula_value_to_pyobject(py, item)?)?;
            }
            Ok(out.into_py(py))
        }
    }
}

pub fn cell_value_to_pyobject(py: Python<'_>, value: CellValue) -> PyObject {
    match value {
        CellValue::Number(v) => v.into_py(py),
        CellValue::Text(v) => v.into_py(py),
        CellValue::Bool(v) => v.into_py(py),
    }
}

pub fn recalc_result_to_pyobject(py: Python<'_>, result: &RecalcResult) -> PyResult<PyObject> {
    let out = PyDict::new(py);
    let ordered_nodes = result
        .ordered_nodes
        .iter()
        .map(|id| id.to_string())
        .collect::<Vec<String>>();
    let levels = result
        .levels
        .iter()
        .map(|level| level.iter().map(|id| id.to_string()).collect::<Vec<String>>())
        .collect::<Vec<Vec<String>>>();

    out.set_item("ordered_nodes", ordered_nodes)?;
    out.set_item("levels", levels)?;
    out.set_item("recalculated_line_items", result.recalculated_line_items)?;
    out.set_item("recalculated_cells", result.recalculated_cells)?;
    Ok(out.into_py(py))
}
