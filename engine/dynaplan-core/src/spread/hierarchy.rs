use std::collections::HashMap;

use rayon::prelude::*;
use uuid::Uuid;

use super::{aggregate_values, SummaryMethod};

pub fn aggregate_hierarchy(
    children_map: &HashMap<Uuid, Vec<Uuid>>,
    initial_values: &HashMap<Uuid, f64>,
    summary_method: SummaryMethod,
) -> HashMap<Uuid, f64> {
    let mut values = initial_values.clone();
    let levels = parent_levels_by_depth_desc(children_map);

    for level in levels {
        let snapshot = values.clone();
        let updates = level
            .par_iter()
            .map(|parent_id| {
                let child_values = children_map
                    .get(parent_id)
                    .cloned()
                    .unwrap_or_default()
                    .into_iter()
                    .map(|child_id| *snapshot.get(&child_id).unwrap_or(&0.0))
                    .collect::<Vec<f64>>();
                (*parent_id, aggregate_values(&child_values, summary_method))
            })
            .collect::<Vec<(Uuid, f64)>>();

        for (parent_id, value) in updates {
            values.insert(parent_id, value);
        }
    }

    values
}

fn parent_levels_by_depth_desc(children_map: &HashMap<Uuid, Vec<Uuid>>) -> Vec<Vec<Uuid>> {
    let parent_index = build_parent_index(children_map);
    let mut depth_cache: HashMap<Uuid, usize> = HashMap::new();
    let mut by_depth: HashMap<usize, Vec<Uuid>> = HashMap::new();

    for parent_id in children_map.keys() {
        let depth = depth_to_root(*parent_id, &parent_index, &mut depth_cache);
        by_depth.entry(depth).or_default().push(*parent_id);
    }

    let mut ordered_depths = by_depth.keys().copied().collect::<Vec<usize>>();
    ordered_depths.sort_unstable_by(|left, right| right.cmp(left));

    ordered_depths
        .into_iter()
        .map(|depth| {
            let mut parents = by_depth.remove(&depth).unwrap_or_default();
            parents.sort_unstable_by_key(|value| value.as_u128());
            parents
        })
        .collect()
}

fn build_parent_index(children_map: &HashMap<Uuid, Vec<Uuid>>) -> HashMap<Uuid, Uuid> {
    let mut index = HashMap::new();
    for (parent_id, children) in children_map {
        for child_id in children {
            index.entry(*child_id).or_insert(*parent_id);
        }
    }
    index
}

fn depth_to_root(
    node_id: Uuid,
    parent_index: &HashMap<Uuid, Uuid>,
    depth_cache: &mut HashMap<Uuid, usize>,
) -> usize {
    if let Some(depth) = depth_cache.get(&node_id).copied() {
        return depth;
    }

    let mut lineage = Vec::new();
    let mut cursor = node_id;
    let mut base_depth = 0usize;

    loop {
        if let Some(cached_depth) = depth_cache.get(&cursor).copied() {
            base_depth = cached_depth;
            break;
        }

        lineage.push(cursor);
        let Some(parent_id) = parent_index.get(&cursor).copied() else {
            break;
        };
        cursor = parent_id;

        if lineage.len() > parent_index.len() + 1 {
            // Defensive break for malformed cyclic structures.
            break;
        }
    }

    let mut depth = base_depth;
    for node in lineage.into_iter().rev() {
        depth_cache.insert(node, depth);
        depth += 1;
    }

    depth_cache.get(&node_id).copied().unwrap_or(0)
}

#[cfg(test)]
mod tests {
    use std::collections::HashMap;

    use uuid::Uuid;

    use super::aggregate_hierarchy;
    use crate::spread::SummaryMethod;

    fn seeded_uuid(seed: u128) -> Uuid {
        Uuid::from_u128(seed + 1)
    }

    #[test]
    fn hierarchy_aggregation_sums_leaf_to_root() {
        let root = seeded_uuid(1);
        let region_a = seeded_uuid(2);
        let region_b = seeded_uuid(3);
        let leaf_a = seeded_uuid(4);
        let leaf_b = seeded_uuid(5);
        let leaf_c = seeded_uuid(6);

        let children_map = HashMap::from([
            (root, vec![region_a, region_b]),
            (region_a, vec![leaf_a, leaf_b]),
            (region_b, vec![leaf_c]),
        ]);

        let initial_values = HashMap::from([(leaf_a, 10.0), (leaf_b, 20.0), (leaf_c, 30.0)]);

        let values = aggregate_hierarchy(&children_map, &initial_values, SummaryMethod::Sum);
        assert_eq!(values.get(&region_a).copied(), Some(30.0));
        assert_eq!(values.get(&region_b).copied(), Some(30.0));
        assert_eq!(values.get(&root).copied(), Some(60.0));
    }

    #[test]
    fn hierarchy_aggregation_uses_summary_method_per_parent() {
        let root = seeded_uuid(11);
        let child_a = seeded_uuid(12);
        let child_b = seeded_uuid(13);

        let children_map = HashMap::from([(root, vec![child_a, child_b])]);
        let initial_values = HashMap::from([(child_a, 25.0), (child_b, 75.0)]);

        let values = aggregate_hierarchy(&children_map, &initial_values, SummaryMethod::Average);
        assert_eq!(values.get(&root).copied(), Some(50.0));
    }
}
