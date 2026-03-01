use std::collections::HashSet;

use uuid::Uuid;

use crate::graph::{sorted_from_set, sorted_from_values, DependencyGraph};

impl DependencyGraph {
    pub fn has_cycle(&self) -> bool {
        !self.detect_cycles().is_empty()
    }

    pub fn detect_cycles(&self) -> Vec<Vec<Uuid>> {
        let mut visited = HashSet::new();
        let mut cycles = Vec::new();
        let mut recorded = HashSet::<Vec<Uuid>>::new();

        for node in sorted_from_set(self.nodes()) {
            if !visited.contains(&node) {
                self.detect_cycles_dfs(
                    node,
                    &mut visited,
                    &mut Vec::new(),
                    &mut HashSet::new(),
                    &mut cycles,
                    &mut recorded,
                );
            }
        }

        cycles
    }

    fn detect_cycles_dfs(
        &self,
        node: Uuid,
        visited: &mut HashSet<Uuid>,
        path: &mut Vec<Uuid>,
        path_set: &mut HashSet<Uuid>,
        cycles: &mut Vec<Vec<Uuid>>,
        recorded: &mut HashSet<Vec<Uuid>>,
    ) {
        visited.insert(node);
        path.push(node);
        path_set.insert(node);

        for neighbour in sorted_from_values(self.get_dependents(&node)) {
            if !self.nodes().contains(&neighbour) {
                continue;
            }

            if path_set.contains(&neighbour) {
                if let Some(cycle_start) = path.iter().position(|id| *id == neighbour) {
                    let mut cycle = path[cycle_start..].to_vec();
                    cycle.push(neighbour);

                    let mut key = cycle[..cycle.len() - 1].to_vec();
                    key.sort_unstable_by_key(|id| id.as_u128());

                    if !recorded.contains(&key) {
                        recorded.insert(key);
                        cycles.push(cycle);
                    }
                }
            } else if !visited.contains(&neighbour) {
                self.detect_cycles_dfs(neighbour, visited, path, path_set, cycles, recorded);
            }
        }

        path.pop();
        path_set.remove(&node);
    }
}
