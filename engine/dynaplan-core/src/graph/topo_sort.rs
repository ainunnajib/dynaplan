use std::collections::HashMap;
use std::error::Error;
use std::fmt;

use uuid::Uuid;

use crate::graph::{sorted_from_set, sorted_from_values, DependencyGraph};

#[derive(Clone, Debug, PartialEq, Eq)]
pub enum GraphError {
    CycleDetected,
}

impl fmt::Display for GraphError {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            GraphError::CycleDetected => write!(
                f,
                "Cycle detected: cannot produce a valid topological order. Call detect_cycles() for details."
            ),
        }
    }
}

impl Error for GraphError {}

impl DependencyGraph {
    pub fn get_calculation_order(&self) -> Result<Vec<Uuid>, GraphError> {
        self.topological_sort_subset(self.nodes())
    }

    pub(crate) fn topological_sort_subset(
        &self,
        nodes: &std::collections::HashSet<Uuid>,
    ) -> Result<Vec<Uuid>, GraphError> {
        let mut in_degree: HashMap<Uuid, usize> =
            nodes.iter().copied().map(|node| (node, 0)).collect();

        for node in sorted_from_set(nodes) {
            for dep in sorted_from_values(self.get_dependencies(&node)) {
                if nodes.contains(&dep) {
                    if let Some(degree) = in_degree.get_mut(&node) {
                        *degree += 1;
                    }
                }
            }
        }

        let mut ready = sorted_from_values(
            in_degree
                .iter()
                .filter_map(|(node, degree)| if *degree == 0 { Some(*node) } else { None }),
        );
        let mut result = Vec::with_capacity(nodes.len());

        while !ready.is_empty() {
            let node = ready.remove(0);
            result.push(node);

            for dependent in sorted_from_values(self.get_dependents(&node)) {
                if !nodes.contains(&dependent) {
                    continue;
                }

                if let Some(degree) = in_degree.get_mut(&dependent) {
                    *degree -= 1;
                    if *degree == 0 {
                        ready.push(dependent);
                    }
                }
            }

            ready.sort_unstable_by_key(|id| id.as_u128());
        }

        if result.len() != nodes.len() {
            return Err(GraphError::CycleDetected);
        }

        Ok(result)
    }
}
