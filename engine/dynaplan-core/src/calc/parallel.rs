use std::collections::{HashMap, HashSet};

use rayon::prelude::*;
use uuid::Uuid;

use crate::graph::DependencyGraph;

pub fn build_topological_levels(graph: &DependencyGraph, ordered_nodes: &[Uuid]) -> Vec<Vec<Uuid>> {
    let mut depth_by_node = HashMap::new();
    let affected = ordered_nodes.iter().copied().collect::<HashSet<Uuid>>();
    let mut levels = Vec::<Vec<Uuid>>::new();

    for node in ordered_nodes {
        let depth = graph
            .get_dependencies(node)
            .into_iter()
            .filter(|dependency| affected.contains(dependency))
            .filter_map(|dependency| depth_by_node.get(&dependency).copied())
            .max()
            .map(|max_depth| max_depth + 1)
            .unwrap_or(0);

        if levels.len() <= depth {
            levels.resize_with(depth + 1, Vec::new);
        }

        levels[depth].push(*node);
        depth_by_node.insert(*node, depth);
    }

    levels
}

pub fn execute_level_parallel<T, E, F>(level: &[Uuid], work: F) -> Result<Vec<T>, E>
where
    T: Send,
    E: Send,
    F: Fn(Uuid) -> Result<T, E> + Send + Sync,
{
    level.par_iter().map(|node| work(*node)).collect()
}
