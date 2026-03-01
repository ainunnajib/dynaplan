use std::collections::{BTreeSet, HashMap, HashSet};

use uuid::Uuid;

use super::{DependencyGraph, GraphError};

type LabelMap = HashMap<String, Uuid>;

fn seeded_uuid(seed: u128) -> Uuid {
    Uuid::from_u128(seed + 1)
}

fn uuid_set(values: &[Uuid]) -> HashSet<Uuid> {
    values.iter().copied().collect()
}

fn label_map_for(labels: &[&str]) -> LabelMap {
    let unique = labels.iter().copied().collect::<BTreeSet<&str>>();
    unique
        .into_iter()
        .enumerate()
        .map(|(idx, label)| (label.to_string(), seeded_uuid(idx as u128 + 1)))
        .collect()
}

fn node(labels: &LabelMap, name: &str) -> Uuid {
    labels
        .get(name)
        .copied()
        .expect("label should have an associated uuid")
}

fn make_graph(edges: &[(&str, &str)]) -> (DependencyGraph, LabelMap) {
    let mut labels = Vec::with_capacity(edges.len() * 2);
    for (dependent, dependency) in edges {
        labels.push(*dependent);
        labels.push(*dependency);
    }

    let label_map = label_map_for(&labels);
    let mut graph = DependencyGraph::new();

    for (dependent, dependency) in edges {
        graph.add_dependency(node(&label_map, dependent), node(&label_map, dependency));
    }

    (graph, label_map)
}

fn valid_topo_order(order: &[Uuid], graph: &DependencyGraph) -> bool {
    let position = order
        .iter()
        .enumerate()
        .map(|(idx, node_id)| (*node_id, idx))
        .collect::<HashMap<Uuid, usize>>();

    for node_id in order {
        for dependency in graph.get_dependencies(node_id) {
            if let Some(dep_index) = position.get(&dependency) {
                if dep_index >= position.get(node_id).expect("node should have position") {
                    return false;
                }
            }
        }
    }

    true
}

fn extract_refs(formula: &str) -> Vec<String> {
    let mut refs = Vec::new();
    let bytes = formula.as_bytes();
    let mut idx = 0usize;

    while idx < bytes.len() {
        if bytes[idx] == b'[' {
            let start = idx + 1;
            if let Some(end_rel) = formula[start..].find(']') {
                let end = start + end_rel;
                if end > start {
                    refs.push(formula[start..end].to_string());
                }
                idx = end + 1;
                continue;
            } else {
                break;
            }
        }

        idx += 1;
    }

    refs
}

fn build_formulas(entries: &[(&str, &str)]) -> (HashMap<Uuid, String>, LabelMap) {
    let labels = entries.iter().map(|(name, _)| *name).collect::<Vec<&str>>();
    let label_map = label_map_for(&labels);
    let formulas = entries
        .iter()
        .map(|(name, formula)| (node(&label_map, name), formula.to_string()))
        .collect::<HashMap<Uuid, String>>();

    (formulas, label_map)
}

#[test]
fn add_single_node() {
    let mut graph = DependencyGraph::new();
    let a = seeded_uuid(1);

    graph.add_node(a);

    assert!(graph.nodes().contains(&a));
}

#[test]
fn add_node_idempotent() {
    let mut graph = DependencyGraph::new();
    let a = seeded_uuid(1);

    graph.add_node(a);
    graph.add_node(a);

    assert_eq!(graph.nodes().len(), 1);
}

#[test]
fn empty_graph_no_errors() {
    let graph = DependencyGraph::new();

    assert_eq!(graph.get_calculation_order().unwrap(), Vec::<Uuid>::new());
    assert_eq!(
        graph.get_recalc_order(HashSet::new()).unwrap(),
        Vec::<Uuid>::new()
    );
    assert_eq!(graph.detect_cycles(), Vec::<Vec<Uuid>>::new());
    assert!(!graph.has_cycle());
}

#[test]
fn single_isolated_node() {
    let mut graph = DependencyGraph::new();
    let x = seeded_uuid(999);
    graph.add_node(x);

    assert_eq!(graph.get_calculation_order().unwrap(), vec![x]);
}

#[test]
fn multiple_isolated_nodes() {
    let mut graph = DependencyGraph::new();
    let labels = label_map_for(&["C", "A", "B"]);
    for name in ["C", "A", "B"] {
        graph.add_node(node(&labels, name));
    }

    let order = graph.get_calculation_order().unwrap();

    assert_eq!(order.len(), 3);
    assert_eq!(
        order.iter().copied().collect::<HashSet<Uuid>>(),
        uuid_set(&[node(&labels, "A"), node(&labels, "B"), node(&labels, "C")])
    );
}

#[test]
fn get_dependencies_direct() {
    let (graph, labels) = make_graph(&[("B", "A")]);
    assert_eq!(
        graph.get_dependencies(&node(&labels, "B")),
        uuid_set(&[node(&labels, "A")])
    );
}

#[test]
fn get_dependents_direct() {
    let (graph, labels) = make_graph(&[("B", "A")]);
    assert_eq!(
        graph.get_dependents(&node(&labels, "A")),
        uuid_set(&[node(&labels, "B")])
    );
}

#[test]
fn get_dependencies_empty_for_root() {
    let (graph, labels) = make_graph(&[("B", "A")]);
    assert_eq!(graph.get_dependencies(&node(&labels, "A")), HashSet::new());
}

#[test]
fn get_dependents_empty_for_leaf() {
    let (graph, labels) = make_graph(&[("B", "A")]);
    assert_eq!(graph.get_dependents(&node(&labels, "B")), HashSet::new());
}

#[test]
fn multiple_dependencies() {
    let mut graph = DependencyGraph::new();
    let labels = label_map_for(&["A", "B", "C"]);
    graph.add_dependency(node(&labels, "C"), node(&labels, "A"));
    graph.add_dependency(node(&labels, "C"), node(&labels, "B"));

    assert_eq!(
        graph.get_dependencies(&node(&labels, "C")),
        uuid_set(&[node(&labels, "A"), node(&labels, "B")])
    );
}

#[test]
fn multiple_dependents() {
    let mut graph = DependencyGraph::new();
    let labels = label_map_for(&["A", "B", "C"]);
    graph.add_dependency(node(&labels, "B"), node(&labels, "A"));
    graph.add_dependency(node(&labels, "C"), node(&labels, "A"));

    assert_eq!(
        graph.get_dependents(&node(&labels, "A")),
        uuid_set(&[node(&labels, "B"), node(&labels, "C")])
    );
}

#[test]
fn unknown_node_returns_empty_set() {
    let graph = DependencyGraph::new();
    let unknown = seeded_uuid(42);
    assert_eq!(graph.get_dependencies(&unknown), HashSet::new());
    assert_eq!(graph.get_dependents(&unknown), HashSet::new());
}

#[test]
fn two_node_chain() {
    let (graph, labels) = make_graph(&[("B", "A")]);
    let order = graph.get_calculation_order().unwrap();
    assert!(
        order
            .iter()
            .position(|id| *id == node(&labels, "A"))
            .expect("A should be in order")
            < order
                .iter()
                .position(|id| *id == node(&labels, "B"))
                .expect("B should be in order")
    );
}

#[test]
fn three_node_chain() {
    let (graph, labels) = make_graph(&[("B", "A"), ("C", "B")]);
    let order = graph.get_calculation_order().unwrap();
    let pos_a = order
        .iter()
        .position(|id| *id == node(&labels, "A"))
        .expect("A should be in order");
    let pos_b = order
        .iter()
        .position(|id| *id == node(&labels, "B"))
        .expect("B should be in order");
    let pos_c = order
        .iter()
        .position(|id| *id == node(&labels, "C"))
        .expect("C should be in order");
    assert!(pos_a < pos_b);
    assert!(pos_b < pos_c);
}

#[test]
fn long_chain() {
    let (graph, labels) = make_graph(&[("B", "A"), ("C", "B"), ("D", "C"), ("E", "D")]);
    let order = graph.get_calculation_order().unwrap();
    assert_eq!(
        order,
        vec![
            node(&labels, "A"),
            node(&labels, "B"),
            node(&labels, "C"),
            node(&labels, "D"),
            node(&labels, "E")
        ]
    );
}

#[test]
fn topo_order_is_valid() {
    let (graph, _) = make_graph(&[("B", "A"), ("C", "B"), ("D", "C")]);
    let order = graph.get_calculation_order().unwrap();
    assert!(valid_topo_order(&order, &graph));
}

#[test]
fn diamond_a_before_b_and_c() {
    let (graph, labels) = make_graph(&[("B", "A"), ("C", "A"), ("D", "B"), ("D", "C")]);
    let order = graph.get_calculation_order().unwrap();
    let pos_a = order
        .iter()
        .position(|id| *id == node(&labels, "A"))
        .expect("A should be in order");
    let pos_b = order
        .iter()
        .position(|id| *id == node(&labels, "B"))
        .expect("B should be in order");
    let pos_c = order
        .iter()
        .position(|id| *id == node(&labels, "C"))
        .expect("C should be in order");
    assert!(pos_a < pos_b);
    assert!(pos_a < pos_c);
}

#[test]
fn diamond_b_and_c_before_d() {
    let (graph, labels) = make_graph(&[("B", "A"), ("C", "A"), ("D", "B"), ("D", "C")]);
    let order = graph.get_calculation_order().unwrap();
    let pos_b = order
        .iter()
        .position(|id| *id == node(&labels, "B"))
        .expect("B should be in order");
    let pos_c = order
        .iter()
        .position(|id| *id == node(&labels, "C"))
        .expect("C should be in order");
    let pos_d = order
        .iter()
        .position(|id| *id == node(&labels, "D"))
        .expect("D should be in order");
    assert!(pos_b < pos_d);
    assert!(pos_c < pos_d);
}

#[test]
fn diamond_all_nodes_present() {
    let (graph, labels) = make_graph(&[("B", "A"), ("C", "A"), ("D", "B"), ("D", "C")]);
    let order = graph.get_calculation_order().unwrap();
    assert_eq!(
        order.iter().copied().collect::<HashSet<Uuid>>(),
        uuid_set(&[
            node(&labels, "A"),
            node(&labels, "B"),
            node(&labels, "C"),
            node(&labels, "D")
        ])
    );
}

#[test]
fn diamond_order_is_valid() {
    let (graph, _) = make_graph(&[("B", "A"), ("C", "A"), ("D", "B"), ("D", "C")]);
    let order = graph.get_calculation_order().unwrap();
    assert!(valid_topo_order(&order, &graph));
}

#[test]
fn change_root_recalcs_all_downstream() {
    let (graph, labels) = make_graph(&[("B", "A"), ("C", "B"), ("D", "C")]);
    let order = graph
        .get_recalc_order(uuid_set(&[node(&labels, "A")]))
        .unwrap();
    assert_eq!(
        order.iter().copied().collect::<HashSet<Uuid>>(),
        uuid_set(&[
            node(&labels, "A"),
            node(&labels, "B"),
            node(&labels, "C"),
            node(&labels, "D")
        ])
    );
    assert!(valid_topo_order(&order, &graph));
}

#[test]
fn change_middle_node_excludes_upstream() {
    let (graph, labels) = make_graph(&[("B", "A"), ("C", "B"), ("D", "C")]);
    let order = graph
        .get_recalc_order(uuid_set(&[node(&labels, "B")]))
        .unwrap();
    assert!(!order.contains(&node(&labels, "A")));
    assert_eq!(
        order.iter().copied().collect::<HashSet<Uuid>>(),
        uuid_set(&[node(&labels, "B"), node(&labels, "C"), node(&labels, "D")])
    );
    assert!(valid_topo_order(&order, &graph));
}

#[test]
fn change_leaf_recalcs_only_leaf() {
    let (graph, labels) = make_graph(&[("B", "A"), ("C", "B")]);
    let order = graph
        .get_recalc_order(uuid_set(&[node(&labels, "C")]))
        .unwrap();
    assert_eq!(order, vec![node(&labels, "C")]);
}

#[test]
fn change_multiple_nodes() {
    let (graph, labels) = make_graph(&[("C", "A"), ("C", "B"), ("D", "C")]);
    let order = graph
        .get_recalc_order(uuid_set(&[node(&labels, "A"), node(&labels, "B")]))
        .unwrap();
    assert_eq!(
        order.iter().copied().collect::<HashSet<Uuid>>(),
        uuid_set(&[
            node(&labels, "A"),
            node(&labels, "B"),
            node(&labels, "C"),
            node(&labels, "D")
        ])
    );
    assert!(valid_topo_order(&order, &graph));
}

#[test]
fn recalc_diamond_change_b() {
    let (graph, labels) = make_graph(&[("B", "A"), ("C", "A"), ("D", "B"), ("D", "C")]);
    let order = graph
        .get_recalc_order(uuid_set(&[node(&labels, "B")]))
        .unwrap();
    assert_eq!(
        order.iter().copied().collect::<HashSet<Uuid>>(),
        uuid_set(&[node(&labels, "B"), node(&labels, "D")])
    );
    assert!(!order.contains(&node(&labels, "A")));
    assert!(!order.contains(&node(&labels, "C")));
}

#[test]
fn recalc_empty_changed_set() {
    let (graph, _) = make_graph(&[("B", "A"), ("C", "B")]);
    assert_eq!(graph.get_recalc_order(HashSet::new()).unwrap(), Vec::<Uuid>::new());
}

#[test]
fn recalc_node_not_in_graph_ignored() {
    let (graph, _) = make_graph(&[("B", "A")]);
    let unknown = seeded_uuid(999_999);
    assert_eq!(
        graph.get_recalc_order(uuid_set(&[unknown])).unwrap(),
        Vec::<Uuid>::new()
    );
}

#[test]
fn no_cycle_returns_empty() {
    let (graph, _) = make_graph(&[("B", "A"), ("C", "B")]);
    assert_eq!(graph.detect_cycles(), Vec::<Vec<Uuid>>::new());
    assert!(!graph.has_cycle());
}

#[test]
fn self_reference() {
    let mut graph = DependencyGraph::new();
    let a = seeded_uuid(1);
    graph.add_dependency(a, a);

    assert!(graph.has_cycle());
    let cycles = graph.detect_cycles();
    assert!(!cycles.is_empty());
    assert!(cycles.iter().any(|cycle| cycle.contains(&a)));
}

#[test]
fn two_node_cycle() {
    let (graph, _) = make_graph(&[("A", "B"), ("B", "A")]);
    assert!(graph.has_cycle());
}

#[test]
fn three_node_cycle() {
    let (graph, labels) = make_graph(&[("B", "A"), ("C", "B"), ("A", "C")]);
    assert!(graph.has_cycle());
    let cycles = graph.detect_cycles();
    let involved = cycles
        .into_iter()
        .flat_map(|cycle| cycle.into_iter())
        .collect::<HashSet<Uuid>>();
    assert!(involved.contains(&node(&labels, "A")));
    assert!(involved.contains(&node(&labels, "B")));
    assert!(involved.contains(&node(&labels, "C")));
}

#[test]
fn cycle_with_external_node() {
    let (graph, labels) = make_graph(&[("B", "A"), ("C", "B"), ("A", "C"), ("B", "D")]);
    assert!(graph.has_cycle());

    for cycle in graph.detect_cycles() {
        assert!(!cycle.contains(&node(&labels, "D")));
    }
}

#[test]
fn topo_sort_raises_on_cycle() {
    let (graph, _) = make_graph(&[("B", "A"), ("A", "B")]);
    assert_eq!(graph.get_calculation_order(), Err(GraphError::CycleDetected));
}

#[test]
fn complex_cycle_detection() {
    let (graph, _) = make_graph(&[
        ("B", "A"),
        ("A", "B"),
        ("D", "C"),
        ("E", "D"),
        ("C", "E"),
    ]);
    assert!(graph.has_cycle());
    let cycles = graph.detect_cycles();
    assert!(cycles.len() >= 2);
}

#[test]
fn remove_middle_node_clears_edges() {
    let (mut graph, labels) = make_graph(&[("B", "A"), ("C", "B")]);
    graph.remove_node(node(&labels, "B"));
    assert!(!graph.nodes().contains(&node(&labels, "B")));
    assert!(!graph.get_dependents(&node(&labels, "A")).contains(&node(&labels, "B")));
    assert!(!graph.get_dependencies(&node(&labels, "C")).contains(&node(&labels, "B")));
}

#[test]
fn remove_nonexistent_node_no_error() {
    let mut graph = DependencyGraph::new();
    graph.remove_node(seeded_uuid(500_000));
}

#[test]
fn remove_then_recalc() {
    let (mut graph, labels) = make_graph(&[("B", "A"), ("C", "B")]);
    graph.remove_node(node(&labels, "B"));
    let order = graph.get_calculation_order().unwrap();
    assert_eq!(
        order.iter().copied().collect::<HashSet<Uuid>>(),
        uuid_set(&[node(&labels, "A"), node(&labels, "C")])
    );
}

#[test]
fn remove_all_nodes() {
    let (mut graph, labels) = make_graph(&[("B", "A"), ("C", "B")]);
    graph.remove_node(node(&labels, "A"));
    graph.remove_node(node(&labels, "B"));
    graph.remove_node(node(&labels, "C"));
    assert_eq!(graph.get_calculation_order().unwrap(), Vec::<Uuid>::new());
}

#[test]
fn remove_node_fixes_cycle() {
    let (mut graph, labels) = make_graph(&[("B", "A"), ("C", "B"), ("A", "C")]);
    assert!(graph.has_cycle());
    graph.remove_node(node(&labels, "C"));
    assert!(!graph.has_cycle());
}

#[test]
fn build_from_formulas_simple_linear() {
    let (formulas, labels) = build_formulas(&[("A", "100"), ("B", "[A] * 2"), ("C", "[B] + 10")]);
    let mut graph = DependencyGraph::new();
    let refs = labels.clone();

    graph.build_from_formulas(&formulas, |formula| {
        extract_refs(formula)
            .into_iter()
            .filter_map(|label| refs.get(&label).copied())
            .collect::<Vec<Uuid>>()
    });

    assert_eq!(
        graph.get_dependencies(&node(&labels, "B")),
        uuid_set(&[node(&labels, "A")])
    );
    assert_eq!(
        graph.get_dependencies(&node(&labels, "C")),
        uuid_set(&[node(&labels, "B")])
    );

    let order = graph.get_calculation_order().unwrap();
    assert!(valid_topo_order(&order, &graph));
}

#[test]
fn build_from_formulas_unknown_references_ignored() {
    let (formulas, labels) = build_formulas(&[("A", "[EXTERNAL] + 1")]);
    let mut refs = labels.clone();
    refs.insert("EXTERNAL".to_string(), seeded_uuid(777_777));

    let mut graph = DependencyGraph::new();
    graph.build_from_formulas(&formulas, |formula| {
        extract_refs(formula)
            .into_iter()
            .filter_map(|label| refs.get(&label).copied())
            .collect::<Vec<Uuid>>()
    });

    assert_eq!(graph.get_dependencies(&node(&labels, "A")), HashSet::new());
}

#[test]
fn build_from_formulas_isolated_node_registered() {
    let (formulas, labels) = build_formulas(&[("A", "42"), ("B", "99")]);
    let refs = labels.clone();
    let mut graph = DependencyGraph::new();

    graph.build_from_formulas(&formulas, |formula| {
        extract_refs(formula)
            .into_iter()
            .filter_map(|label| refs.get(&label).copied())
            .collect::<Vec<Uuid>>()
    });

    assert!(graph.nodes().contains(&node(&labels, "A")));
    assert!(graph.nodes().contains(&node(&labels, "B")));
}

#[test]
fn build_from_formulas_detects_cycle() {
    let (formulas, labels) = build_formulas(&[("A", "[B] + 1"), ("B", "[A] * 2")]);
    let refs = labels.clone();
    let mut graph = DependencyGraph::new();
    graph.build_from_formulas(&formulas, |formula| {
        extract_refs(formula)
            .into_iter()
            .filter_map(|label| refs.get(&label).copied())
            .collect::<Vec<Uuid>>()
    });
    assert!(graph.has_cycle());
}

#[test]
fn build_from_formulas_complex_model() {
    let (formulas, labels) = build_formulas(&[
        ("Revenue", "100"),
        ("COGS", "[Revenue] * 0.6"),
        ("GrossProfit", "[Revenue] - [COGS]"),
        ("Opex", "20"),
        ("EBIT", "[GrossProfit] - [Opex]"),
    ]);
    let refs = labels.clone();
    let mut graph = DependencyGraph::new();
    graph.build_from_formulas(&formulas, |formula| {
        extract_refs(formula)
            .into_iter()
            .filter_map(|label| refs.get(&label).copied())
            .collect::<Vec<Uuid>>()
    });

    let order = graph.get_calculation_order().unwrap();
    assert!(valid_topo_order(&order, &graph));
    let pos_revenue = order
        .iter()
        .position(|id| *id == node(&labels, "Revenue"))
        .expect("Revenue should be in order");
    let pos_cogs = order
        .iter()
        .position(|id| *id == node(&labels, "COGS"))
        .expect("COGS should be in order");
    let pos_gp = order
        .iter()
        .position(|id| *id == node(&labels, "GrossProfit"))
        .expect("GrossProfit should be in order");
    let pos_ebit = order
        .iter()
        .position(|id| *id == node(&labels, "EBIT"))
        .expect("EBIT should be in order");
    assert!(pos_revenue < pos_cogs);
    assert!(pos_cogs < pos_gp);
    assert!(pos_gp < pos_ebit);
}

#[test]
fn disconnected_two_chains_independently_sorted() {
    let (graph, labels) =
        make_graph(&[("B", "A"), ("C", "B"), ("Y", "X"), ("Z", "Y")]);
    let order = graph.get_calculation_order().unwrap();
    assert_eq!(
        order.iter().copied().collect::<HashSet<Uuid>>(),
        uuid_set(&[
            node(&labels, "A"),
            node(&labels, "B"),
            node(&labels, "C"),
            node(&labels, "X"),
            node(&labels, "Y"),
            node(&labels, "Z")
        ])
    );
    assert!(valid_topo_order(&order, &graph));
}

#[test]
fn disconnected_recalc_affects_one_component() {
    let (graph, labels) =
        make_graph(&[("B", "A"), ("C", "B"), ("Y", "X"), ("Z", "Y")]);
    let order = graph
        .get_recalc_order(uuid_set(&[node(&labels, "A")]))
        .unwrap();
    assert_eq!(
        order.iter().copied().collect::<HashSet<Uuid>>(),
        uuid_set(&[node(&labels, "A"), node(&labels, "B"), node(&labels, "C")])
    );
    assert!(!order.contains(&node(&labels, "X")));
    assert!(!order.contains(&node(&labels, "Y")));
    assert!(!order.contains(&node(&labels, "Z")));
}

#[test]
fn large_100_node_linear_chain_order() {
    let mut graph = DependencyGraph::new();
    let nodes = (0..100)
        .map(|idx| seeded_uuid(10_000 + idx as u128))
        .collect::<Vec<Uuid>>();

    for idx in 1..100 {
        graph.add_dependency(nodes[idx], nodes[idx - 1]);
    }

    let order = graph.get_calculation_order().unwrap();
    assert_eq!(order.len(), 100);
    assert!(valid_topo_order(&order, &graph));
    assert_eq!(order[0], nodes[0]);
    assert_eq!(order.iter().copied().collect::<HashSet<Uuid>>(), uuid_set(&nodes));
}

#[test]
fn large_100_node_fan_out_then_in() {
    let mut graph = DependencyGraph::new();
    let root = seeded_uuid(20_000);
    let sink = seeded_uuid(20_001);
    graph.add_node(root);
    graph.add_node(sink);

    for idx in 0..99 {
        let leaf = seeded_uuid(21_000 + idx as u128);
        graph.add_dependency(leaf, root);
        graph.add_dependency(sink, leaf);
    }

    let order = graph.get_calculation_order().unwrap();
    assert_eq!(order.len(), 101);
    assert!(valid_topo_order(&order, &graph));
    assert_eq!(order[0], root);
    assert_eq!(order[order.len() - 1], sink);
}

#[test]
fn large_graph_partial_recalc_minimal() {
    let mut graph = DependencyGraph::new();
    let chain1 = (0..50)
        .map(|idx| seeded_uuid(30_000 + idx as u128))
        .collect::<Vec<Uuid>>();
    let chain2 = (0..50)
        .map(|idx| seeded_uuid(40_000 + idx as u128))
        .collect::<Vec<Uuid>>();

    for idx in 1..50 {
        graph.add_dependency(chain1[idx], chain1[idx - 1]);
        graph.add_dependency(chain2[idx], chain2[idx - 1]);
    }

    let changed = uuid_set(&[chain1[10]]);
    let order = graph.get_recalc_order(changed).unwrap();
    assert_eq!(order.len(), 40);
    for node_id in &order {
        assert!(chain1.contains(node_id));
    }
    assert!(valid_topo_order(&order, &graph));
}
