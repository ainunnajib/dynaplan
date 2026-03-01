use std::collections::{HashMap, HashSet};

use uuid::Uuid;

pub mod cycle_detect;
pub mod recalc;
pub mod topo_sort;

pub use topo_sort::GraphError;

#[derive(Clone, Debug, Default)]
pub struct DependencyGraph {
    nodes: HashSet<Uuid>,
    deps: HashMap<Uuid, HashSet<Uuid>>,
    dependents: HashMap<Uuid, HashSet<Uuid>>,
}

impl DependencyGraph {
    pub fn new() -> Self {
        Self::default()
    }

    pub fn add_node(&mut self, node_id: Uuid) {
        self.nodes.insert(node_id);
        self.deps.entry(node_id).or_insert_with(HashSet::new);
        self.dependents
            .entry(node_id)
            .or_insert_with(HashSet::new);
    }

    pub fn add_dependency(&mut self, node_id: Uuid, depends_on: Uuid) {
        self.add_node(node_id);
        self.add_node(depends_on);
        self.deps
            .entry(node_id)
            .or_insert_with(HashSet::new)
            .insert(depends_on);
        self.dependents
            .entry(depends_on)
            .or_insert_with(HashSet::new)
            .insert(node_id);
    }

    pub fn remove_node(&mut self, node_id: Uuid) {
        if !self.nodes.contains(&node_id) {
            return;
        }

        if let Some(node_deps) = self.deps.get(&node_id).cloned() {
            for dep in node_deps {
                if let Some(dependents) = self.dependents.get_mut(&dep) {
                    dependents.remove(&node_id);
                }
            }
        }

        if let Some(node_dependents) = self.dependents.get(&node_id).cloned() {
            for dependent in node_dependents {
                if let Some(deps) = self.deps.get_mut(&dependent) {
                    deps.remove(&node_id);
                }
            }
        }

        self.deps.remove(&node_id);
        self.dependents.remove(&node_id);
        self.nodes.remove(&node_id);
    }

    pub fn get_dependencies(&self, node_id: &Uuid) -> HashSet<Uuid> {
        self.deps.get(node_id).cloned().unwrap_or_default()
    }

    pub fn get_dependents(&self, node_id: &Uuid) -> HashSet<Uuid> {
        self.dependents.get(node_id).cloned().unwrap_or_default()
    }

    pub fn nodes(&self) -> &HashSet<Uuid> {
        &self.nodes
    }

    pub fn build_from_formulas<F, I>(&mut self, formulas: &HashMap<Uuid, String>, mut get_references: F)
    where
        F: FnMut(&str) -> I,
        I: IntoIterator<Item = Uuid>,
    {
        for node_id in formulas.keys() {
            self.add_node(*node_id);
        }

        for (node_id, formula_text) in formulas {
            for reference in get_references(formula_text) {
                if formulas.contains_key(&reference) {
                    self.add_dependency(*node_id, reference);
                }
            }
        }
    }
}

pub(crate) fn sorted_from_set(nodes: &HashSet<Uuid>) -> Vec<Uuid> {
    let mut ordered = nodes.iter().copied().collect::<Vec<Uuid>>();
    ordered.sort_unstable_by_key(|id| id.as_u128());
    ordered
}

pub(crate) fn sorted_from_values<I>(values: I) -> Vec<Uuid>
where
    I: IntoIterator<Item = Uuid>,
{
    let mut ordered = values.into_iter().collect::<Vec<Uuid>>();
    ordered.sort_unstable_by_key(|id| id.as_u128());
    ordered
}

#[cfg(test)]
mod tests;
