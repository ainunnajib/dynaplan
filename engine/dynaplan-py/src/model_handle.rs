use std::sync::{Arc, RwLock, RwLockReadGuard, RwLockWriteGuard};

use dynaplan_core::{DependencyGraph, ModelState, RecalcOrchestrator};
use pyo3::exceptions::PyRuntimeError;
use pyo3::prelude::*;

#[derive(Clone, Debug, Default)]
pub struct EngineState {
    pub model: ModelState,
    pub graph: DependencyGraph,
    pub orchestrator: RecalcOrchestrator,
}

#[pyclass(name = "ModelHandle")]
#[derive(Clone)]
pub struct ModelHandle {
    pub(crate) state: Arc<RwLock<EngineState>>,
}

#[pymethods]
impl ModelHandle {
    #[new]
    pub fn py_new() -> Self {
        Self::from_state(EngineState::default())
    }

    fn __repr__(&self) -> PyResult<String> {
        let guard = self.read()?;
        Ok(format!(
            "ModelHandle(blocks={}, dimensions={}, nodes={})",
            guard.model.block_count(),
            guard.model.dimension_count(),
            guard.graph.nodes().len()
        ))
    }
}

impl ModelHandle {
    pub fn from_state(state: EngineState) -> Self {
        Self {
            state: Arc::new(RwLock::new(state)),
        }
    }

    pub fn read(&self) -> PyResult<RwLockReadGuard<'_, EngineState>> {
        self.state
            .read()
            .map_err(|_| PyRuntimeError::new_err("ModelHandle read lock poisoned"))
    }

    pub fn write(&self) -> PyResult<RwLockWriteGuard<'_, EngineState>> {
        self.state
            .write()
            .map_err(|_| PyRuntimeError::new_err("ModelHandle write lock poisoned"))
    }
}
