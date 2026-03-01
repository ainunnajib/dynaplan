use std::collections::{HashSet, VecDeque};

use uuid::Uuid;

use crate::graph::{sorted_from_values, DependencyGraph, GraphError};

impl DependencyGraph {
    pub fn get_recalc_order(&self, changed_nodes: HashSet<Uuid>) -> Result<Vec<Uuid>, GraphError> {
        let affected = self.downstream_set(&changed_nodes);
        self.topological_sort_subset(&affected)
    }

    pub(crate) fn downstream_set(&self, start_nodes: &HashSet<Uuid>) -> HashSet<Uuid> {
        let mut visited = HashSet::new();
        let mut queue = VecDeque::new();

        for node in sorted_from_values(start_nodes.iter().copied()) {
            if self.nodes().contains(&node) {
                queue.push_back(node);
                visited.insert(node);
            }
        }

        while let Some(node) = queue.pop_front() {
            for dependent in sorted_from_values(self.get_dependents(&node)) {
                if self.nodes().contains(&dependent) && !visited.contains(&dependent) {
                    visited.insert(dependent);
                    queue.push_back(dependent);
                }
            }
        }

        visited
    }
}
