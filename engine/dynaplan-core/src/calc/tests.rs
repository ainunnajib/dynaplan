use std::collections::{HashMap, HashSet};

use uuid::Uuid;

use super::{
    average_slice, build_cell_context, build_topological_levels, collect_recalc_keys, count_slice,
    execute_level_parallel, sum_slice, CalcError, FormulaSpec, RecalcOrchestrator,
};
use crate::{CalculationBlock, CellValue, DependencyGraph, DimensionDef, DimensionKey, ModelState};

fn seeded_uuid(seed: u128) -> Uuid {
    Uuid::from_u128(seed + 1)
}

fn key(seed: u128) -> DimensionKey {
    DimensionKey::new(vec![seeded_uuid(seed)])
}

fn build_dimensions(
    model: &mut ModelState,
    dimension_count: usize,
    members_per_dimension: usize,
) -> Vec<Vec<Uuid>> {
    let mut dimension_members = Vec::with_capacity(dimension_count);

    for dim_idx in 0..dimension_count {
        let dimension_id = seeded_uuid(10_000 + dim_idx as u128);
        let members = (0..members_per_dimension)
            .map(|member_idx| seeded_uuid(((dim_idx as u128 + 1) << 32) + member_idx as u128))
            .collect::<Vec<Uuid>>();

        model.upsert_dimension(DimensionDef::new(dimension_id, members.clone()));
        dimension_members.push(members);
    }

    dimension_members
}

fn key_for_index(mut index: usize, dimension_members: &[Vec<Uuid>]) -> DimensionKey {
    let mut members = Vec::with_capacity(dimension_members.len());

    for members_for_dimension in dimension_members {
        let member_index = index % members_for_dimension.len();
        members.push(members_for_dimension[member_index]);
        index /= members_for_dimension.len();
    }

    DimensionKey::new(members)
}

#[test]
fn build_levels_groups_nodes_by_depth() {
    let a = seeded_uuid(1);
    let b = seeded_uuid(2);
    let c = seeded_uuid(3);
    let d = seeded_uuid(4);

    let mut graph = DependencyGraph::new();
    graph.add_dependency(b, a);
    graph.add_dependency(c, a);
    graph.add_dependency(d, b);
    graph.add_dependency(d, c);

    let order = graph.get_calculation_order().unwrap();
    let levels = build_topological_levels(&graph, &order);

    assert_eq!(levels, vec![vec![a], vec![b, c], vec![d]]);
}

#[test]
fn collect_recalc_keys_uses_target_and_dependency_blocks() {
    let target = seeded_uuid(11);
    let source = seeded_uuid(12);
    let target_key = key(200);
    let source_key = key(100);

    let mut target_block = CalculationBlock::new(target);
    target_block.write_numeric(target_key.clone(), 3.0);

    let mut source_block = CalculationBlock::new(source);
    source_block.write_numeric(source_key.clone(), 7.0);

    let blocks = HashMap::from([(target, target_block), (source, source_block)]);
    let formula = FormulaSpec::new("SRC + 1", HashMap::from([("SRC".to_string(), source)]));

    let keys = collect_recalc_keys(&target, &formula, &blocks);

    assert_eq!(keys, vec![source_key, target_key]);
}

#[test]
fn build_cell_context_reads_sparse_blocks_and_defaults_to_zero() {
    let source_a = seeded_uuid(21);
    let source_b = seeded_uuid(22);
    let existing_key = key(333);
    let missing_key = key(334);

    let mut block_a = CalculationBlock::new(source_a);
    block_a.write_numeric(existing_key.clone(), 42.0);

    let blocks = HashMap::from([(source_a, block_a), (source_b, CalculationBlock::new(source_b))]);
    let formula = FormulaSpec::new(
        "A + B",
        HashMap::from([("A".to_string(), source_a), ("B".to_string(), source_b)]),
    );

    let existing_context = build_cell_context(&formula, &existing_key, &blocks);
    assert_eq!(
        existing_context.get("A"),
        Some(&CellValue::Number(42.0))
    );
    assert_eq!(existing_context.get("B"), Some(&CellValue::Number(0.0)));

    let missing_context = build_cell_context(&formula, &missing_key, &blocks);
    assert_eq!(missing_context.get("A"), Some(&CellValue::Number(0.0)));
    assert_eq!(missing_context.get("B"), Some(&CellValue::Number(0.0)));
}

#[test]
fn execute_level_parallel_runs_each_node() {
    let nodes = vec![seeded_uuid(91), seeded_uuid(92), seeded_uuid(93)];
    let results = execute_level_parallel(&nodes, |node| -> Result<Uuid, ()> { Ok(node) }).unwrap();
    let result_set = results.into_iter().collect::<HashSet<Uuid>>();
    let expected_set = nodes.into_iter().collect::<HashSet<Uuid>>();
    assert_eq!(result_set, expected_set);
}

#[test]
fn recalc_updates_only_downstream_formula_nodes() {
    let input = seeded_uuid(100);
    let doubled = seeded_uuid(101);
    let plus_one = seeded_uuid(102);
    let cell_key = key(444);

    let mut graph = DependencyGraph::new();
    graph.add_dependency(doubled, input);
    graph.add_dependency(plus_one, doubled);

    let formulas = HashMap::from([
        (
            doubled,
            FormulaSpec::new("INPUT * 2", HashMap::from([("INPUT".to_string(), input)])),
        ),
        (
            plus_one,
            FormulaSpec::new("DBL + 1", HashMap::from([("DBL".to_string(), doubled)])),
        ),
    ]);

    let mut model = ModelState::new();
    model.write_numeric_cell(input, cell_key.clone(), 5.0);
    model.write_numeric_cell(doubled, cell_key.clone(), 0.0);
    model.write_numeric_cell(plus_one, cell_key.clone(), 0.0);

    let orchestrator = RecalcOrchestrator::new(formulas);
    let result = orchestrator
        .recalc(&mut model, &graph, vec![(input, cell_key.clone())])
        .unwrap();

    assert_eq!(model.read_numeric_cell(&input, &cell_key), Some(5.0));
    assert_eq!(model.read_numeric_cell(&doubled, &cell_key), Some(10.0));
    assert_eq!(model.read_numeric_cell(&plus_one, &cell_key), Some(11.0));
    assert_eq!(result.ordered_nodes, vec![input, doubled, plus_one]);
    assert_eq!(result.levels, vec![vec![input], vec![doubled], vec![plus_one]]);
    assert_eq!(result.recalculated_line_items, 2);
    assert_eq!(result.recalculated_cells, 2);
}

#[test]
fn recalc_parallel_level_handles_sibling_blocks() {
    let input = seeded_uuid(120);
    let left = seeded_uuid(121);
    let right = seeded_uuid(122);
    let cell_key = key(555);

    let mut graph = DependencyGraph::new();
    graph.add_dependency(left, input);
    graph.add_dependency(right, input);

    let formulas = HashMap::from([
        (
            left,
            FormulaSpec::new("A * 2", HashMap::from([("A".to_string(), input)])),
        ),
        (
            right,
            FormulaSpec::new("A * 3", HashMap::from([("A".to_string(), input)])),
        ),
    ]);

    let mut model = ModelState::new();
    model.write_numeric_cell(input, cell_key.clone(), 4.0);

    let orchestrator = RecalcOrchestrator::new(formulas);
    let result = orchestrator
        .recalc(&mut model, &graph, vec![(input, cell_key.clone())])
        .unwrap();

    assert_eq!(model.read_numeric_cell(&left, &cell_key), Some(8.0));
    assert_eq!(model.read_numeric_cell(&right, &cell_key), Some(12.0));
    assert_eq!(result.levels, vec![vec![input], vec![left, right]]);
}

#[test]
fn recalc_rejects_non_numeric_formula_results() {
    let input = seeded_uuid(130);
    let text_node = seeded_uuid(131);
    let cell_key = key(556);

    let mut graph = DependencyGraph::new();
    graph.add_dependency(text_node, input);

    let formulas = HashMap::from([(
        text_node,
        FormulaSpec::new(
            "IF(A > 0, \"ok\", \"no\")",
            HashMap::from([("A".to_string(), input)]),
        ),
    )]);

    let mut model = ModelState::new();
    model.write_numeric_cell(input, cell_key.clone(), 1.0);

    let orchestrator = RecalcOrchestrator::new(formulas);
    let err = orchestrator
        .recalc(&mut model, &graph, vec![(input, cell_key)])
        .expect_err("text-producing formula should fail numeric block write");

    match err {
        CalcError::NonNumericResult { line_item_id, .. } => assert_eq!(line_item_id, text_node),
        other => panic!("unexpected error: {:?}", other),
    }
}

#[test]
fn recalc_validates_missing_reference_bindings() {
    let input = seeded_uuid(140);
    let broken = seeded_uuid(141);
    let cell_key = key(557);

    let mut graph = DependencyGraph::new();
    graph.add_dependency(broken, input);

    let formulas = HashMap::from([(broken, FormulaSpec::new("INPUT + 1", HashMap::new()))]);
    let mut model = ModelState::new();
    model.write_numeric_cell(input, cell_key.clone(), 2.0);

    let orchestrator = RecalcOrchestrator::new(formulas);
    let err = orchestrator
        .recalc(&mut model, &graph, vec![(input, cell_key)])
        .expect_err("missing reference mapping should be rejected");

    match err {
        CalcError::MissingReferenceBinding {
            line_item_id,
            identifier,
        } => {
            assert_eq!(line_item_id, broken);
            assert_eq!(identifier, "INPUT".to_string());
        }
        other => panic!("unexpected error: {:?}", other),
    }
}

#[test]
fn aggregation_helpers_support_sum_average_and_count() {
    let values = (1..=10).map(|v| v as f64).collect::<Vec<f64>>();

    assert_eq!(sum_slice(&values), 55.0);
    assert_eq!(average_slice(&values), Some(5.5));
    assert_eq!(count_slice(&values), 10);
    assert_eq!(average_slice(&[]), None);
}

#[test]
fn recalc_returns_default_for_empty_change_set() {
    let mut model = ModelState::new();
    let graph = DependencyGraph::new();
    let orchestrator = RecalcOrchestrator::default();

    let result = orchestrator.recalc(&mut model, &graph, Vec::new()).unwrap();
    assert!(result.ordered_nodes.is_empty());
    assert!(result.levels.is_empty());
    assert_eq!(result.recalculated_line_items, 0);
    assert_eq!(result.recalculated_cells, 0);
}

#[test]
#[ignore = "stress test for 100K cells across 50 dependent line items"]
fn recalc_100k_cells_across_50_line_items_matches_expected_values() {
    let mut model = ModelState::new();
    let dimension_members = build_dimensions(&mut model, 5, 10);
    let line_items = (0..50)
        .map(|idx| seeded_uuid(1_000 + idx as u128))
        .collect::<Vec<Uuid>>();

    let mut graph = DependencyGraph::new();
    graph.add_node(line_items[0]);

    let mut formulas = HashMap::new();
    for idx in 1..line_items.len() {
        graph.add_dependency(line_items[idx], line_items[idx - 1]);
        formulas.insert(
            line_items[idx],
            FormulaSpec::new(
                format!("L{} + 1", idx - 1),
                HashMap::from([(format!("L{}", idx - 1), line_items[idx - 1])]),
            ),
        );
    }

    let mut changed_key = None;
    for index in 0..100_000usize {
        let dim_key = key_for_index(index, &dimension_members);
        model.write_numeric_cell(line_items[0], dim_key.clone(), index as f64);
        if index == 0 {
            changed_key = Some(dim_key);
        }
    }

    let orchestrator = RecalcOrchestrator::new(formulas);
    let result = orchestrator
        .recalc(
            &mut model,
            &graph,
            vec![(line_items[0], changed_key.expect("changed key should exist"))],
        )
        .unwrap();

    for sample_index in [0usize, 1, 17, 999, 42_424, 99_999] {
        let dim_key = key_for_index(sample_index, &dimension_members);
        assert_eq!(
            model.read_numeric_cell(line_items.last().unwrap(), &dim_key),
            Some(sample_index as f64 + 49.0)
        );
    }

    assert_eq!(result.recalculated_line_items, 49);
    assert_eq!(result.recalculated_cells, 4_900_000);
}
