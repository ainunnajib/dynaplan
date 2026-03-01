"""
Tests for F007: Calculation Dependency Graph

All tests are self-contained — no database, no HTTP, no FastAPI.
"""

import pytest
from typing import List

from app.engine.dependency_graph import DependencyGraph


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_graph(*edges) -> DependencyGraph:
    """
    Convenience factory.  Each edge is a tuple (dependent, dependency),
    meaning `dependent` depends on `dependency`.
    e.g. ("B", "A") means B's formula references A.
    """
    g = DependencyGraph()
    for dependent, dependency in edges:
        g.add_dependency(dependent, dependency)
    return g


def valid_topo_order(order: List[str], graph: DependencyGraph) -> bool:
    """
    Verify that every dependency of a node appears before that node in the
    given order.
    """
    position = {node: i for i, node in enumerate(order)}
    for node in order:
        for dep in graph.get_dependencies(node):
            if dep in position and position[dep] >= position[node]:
                return False
    return True


# ---------------------------------------------------------------------------
# 1. Basic node registration
# ---------------------------------------------------------------------------

class TestBasicNodes:
    def test_add_single_node(self):
        g = DependencyGraph()
        g.add_node("A")
        assert "A" in g._nodes

    def test_add_node_idempotent(self):
        g = DependencyGraph()
        g.add_node("A")
        g.add_node("A")
        assert len(g._nodes) == 1

    def test_empty_graph_no_errors(self):
        g = DependencyGraph()
        assert g.get_calculation_order() == []
        assert g.get_recalc_order(set()) == []
        assert g.detect_cycles() == []
        assert g.has_cycle() is False

    def test_single_isolated_node(self):
        g = DependencyGraph()
        g.add_node("X")
        order = g.get_calculation_order()
        assert order == ["X"]

    def test_multiple_isolated_nodes(self):
        g = DependencyGraph()
        for n in ["C", "A", "B"]:
            g.add_node(n)
        order = g.get_calculation_order()
        assert set(order) == {"A", "B", "C"}
        assert len(order) == 3


# ---------------------------------------------------------------------------
# 2. Dependency / dependent queries
# ---------------------------------------------------------------------------

class TestEdgeQueries:
    def test_get_dependencies_direct(self):
        g = make_graph(("B", "A"))
        assert g.get_dependencies("B") == {"A"}

    def test_get_dependents_direct(self):
        g = make_graph(("B", "A"))
        assert g.get_dependents("A") == {"B"}

    def test_get_dependencies_empty_for_root(self):
        g = make_graph(("B", "A"))
        assert g.get_dependencies("A") == set()

    def test_get_dependents_empty_for_leaf(self):
        g = make_graph(("B", "A"))
        assert g.get_dependents("B") == set()

    def test_multiple_dependencies(self):
        # C = A + B
        g = DependencyGraph()
        g.add_dependency("C", "A")
        g.add_dependency("C", "B")
        assert g.get_dependencies("C") == {"A", "B"}

    def test_multiple_dependents(self):
        # A is used by B and C
        g = DependencyGraph()
        g.add_dependency("B", "A")
        g.add_dependency("C", "A")
        assert g.get_dependents("A") == {"B", "C"}

    def test_unknown_node_returns_empty_set(self):
        g = DependencyGraph()
        assert g.get_dependencies("nonexistent") == set()
        assert g.get_dependents("nonexistent") == set()


# ---------------------------------------------------------------------------
# 3. Topological sort — linear chain
# ---------------------------------------------------------------------------

class TestTopoLinearChain:
    def test_two_node_chain(self):
        g = make_graph(("B", "A"))
        order = g.get_calculation_order()
        assert order.index("A") < order.index("B")

    def test_three_node_chain(self):
        # A -> B -> C  (C depends on B depends on A)
        g = make_graph(("B", "A"), ("C", "B"))
        order = g.get_calculation_order()
        assert order.index("A") < order.index("B")
        assert order.index("B") < order.index("C")

    def test_long_chain(self):
        # A -> B -> C -> D -> E
        g = make_graph(("B", "A"), ("C", "B"), ("D", "C"), ("E", "D"))
        order = g.get_calculation_order()
        for i, node in enumerate(["A", "B", "C", "D", "E"]):
            assert order.index(node) == i

    def test_topo_order_is_valid(self):
        g = make_graph(("B", "A"), ("C", "B"), ("D", "C"))
        order = g.get_calculation_order()
        assert valid_topo_order(order, g)


# ---------------------------------------------------------------------------
# 4. Topological sort — diamond shape
# ---------------------------------------------------------------------------

class TestTopoDiamond:
    """
    A -> B
    A -> C
    B -> D
    C -> D
    (B and C both depend on A; D depends on both B and C)
    """

    def setup_method(self):
        self.g = make_graph(("B", "A"), ("C", "A"), ("D", "B"), ("D", "C"))

    def test_diamond_a_before_b_and_c(self):
        order = self.g.get_calculation_order()
        assert order.index("A") < order.index("B")
        assert order.index("A") < order.index("C")

    def test_diamond_b_and_c_before_d(self):
        order = self.g.get_calculation_order()
        assert order.index("B") < order.index("D")
        assert order.index("C") < order.index("D")

    def test_diamond_all_nodes_present(self):
        order = self.g.get_calculation_order()
        assert set(order) == {"A", "B", "C", "D"}

    def test_diamond_order_is_valid(self):
        order = self.g.get_calculation_order()
        assert valid_topo_order(order, self.g)


# ---------------------------------------------------------------------------
# 5. Partial recalculation
# ---------------------------------------------------------------------------

class TestPartialRecalc:
    def test_change_root_recalcs_all_downstream(self):
        # A -> B -> C -> D
        g = make_graph(("B", "A"), ("C", "B"), ("D", "C"))
        order = g.get_recalc_order({"A"})
        assert set(order) == {"A", "B", "C", "D"}
        assert valid_topo_order(order, g)

    def test_change_middle_node_excludes_upstream(self):
        # A -> B -> C -> D;  changing B should NOT recalc A
        g = make_graph(("B", "A"), ("C", "B"), ("D", "C"))
        order = g.get_recalc_order({"B"})
        assert "A" not in order
        assert set(order) == {"B", "C", "D"}
        assert valid_topo_order(order, g)

    def test_change_leaf_recalcs_only_leaf(self):
        # A -> B -> C;  changing C (leaf) only recalcs C
        g = make_graph(("B", "A"), ("C", "B"))
        order = g.get_recalc_order({"C"})
        assert order == ["C"]

    def test_change_multiple_nodes(self):
        # A -> C, B -> C, C -> D
        g = make_graph(("C", "A"), ("C", "B"), ("D", "C"))
        order = g.get_recalc_order({"A", "B"})
        assert set(order) == {"A", "B", "C", "D"}
        assert valid_topo_order(order, g)

    def test_recalc_diamond_change_b(self):
        # A -> B, A -> C, B -> D, C -> D;  change B => {B, D}
        g = make_graph(("B", "A"), ("C", "A"), ("D", "B"), ("D", "C"))
        order = g.get_recalc_order({"B"})
        assert set(order) == {"B", "D"}
        assert "A" not in order
        assert "C" not in order

    def test_recalc_empty_changed_set(self):
        g = make_graph(("B", "A"), ("C", "B"))
        assert g.get_recalc_order(set()) == []

    def test_recalc_node_not_in_graph_ignored(self):
        g = make_graph(("B", "A"))
        # "Z" is not in the graph — should not raise, just ignored
        order = g.get_recalc_order({"Z"})
        assert order == []


# ---------------------------------------------------------------------------
# 6. Cycle detection
# ---------------------------------------------------------------------------

class TestCycleDetection:
    def test_no_cycle_returns_empty(self):
        g = make_graph(("B", "A"), ("C", "B"))
        assert g.detect_cycles() == []
        assert g.has_cycle() is False

    def test_self_reference(self):
        g = DependencyGraph()
        g.add_dependency("A", "A")
        assert g.has_cycle() is True
        cycles = g.detect_cycles()
        assert len(cycles) >= 1
        # The cycle must involve A
        assert any("A" in cycle for cycle in cycles)

    def test_two_node_cycle(self):
        # A depends on B, B depends on A
        g = make_graph(("A", "B"), ("B", "A"))
        assert g.has_cycle() is True

    def test_three_node_cycle(self):
        # A -> B -> C -> A
        g = make_graph(("B", "A"), ("C", "B"), ("A", "C"))
        assert g.has_cycle() is True
        cycles = g.detect_cycles()
        involved = {node for cycle in cycles for node in cycle}
        assert {"A", "B", "C"}.issubset(involved)

    def test_cycle_with_external_node(self):
        # A -> B -> C -> A  (cycle),  D -> B  (D outside cycle)
        g = make_graph(("B", "A"), ("C", "B"), ("A", "C"), ("B", "D"))
        assert g.has_cycle() is True
        # D should not be part of the cycle
        cycles = g.detect_cycles()
        for cycle in cycles:
            assert "D" not in cycle

    def test_topo_sort_raises_on_cycle(self):
        g = make_graph(("B", "A"), ("A", "B"))
        with pytest.raises(ValueError, match="Cycle detected"):
            g.get_calculation_order()

    def test_complex_cycle_detection(self):
        # Two separate cycles: A-B-A and C-D-E-C
        g = make_graph(
            ("B", "A"), ("A", "B"),  # cycle 1
            ("D", "C"), ("E", "D"), ("C", "E"),  # cycle 2
        )
        assert g.has_cycle() is True
        cycles = g.detect_cycles()
        assert len(cycles) >= 2


# ---------------------------------------------------------------------------
# 7. Remove node
# ---------------------------------------------------------------------------

class TestRemoveNode:
    def test_remove_middle_node_clears_edges(self):
        # A -> B -> C
        g = make_graph(("B", "A"), ("C", "B"))
        g.remove_node("B")
        assert "B" not in g._nodes
        # A no longer has B as a dependent
        assert "B" not in g.get_dependents("A")
        # C no longer depends on B
        assert "B" not in g.get_dependencies("C")

    def test_remove_nonexistent_node_no_error(self):
        g = DependencyGraph()
        g.remove_node("ghost")  # must not raise

    def test_remove_then_recalc(self):
        g = make_graph(("B", "A"), ("C", "B"))
        g.remove_node("B")
        # A and C are now isolated
        order = g.get_calculation_order()
        assert set(order) == {"A", "C"}

    def test_remove_all_nodes(self):
        g = make_graph(("B", "A"), ("C", "B"))
        g.remove_node("A")
        g.remove_node("B")
        g.remove_node("C")
        assert g.get_calculation_order() == []

    def test_remove_node_fixes_cycle(self):
        # A -> B -> C -> A  (cycle); remove C fixes it
        g = make_graph(("B", "A"), ("C", "B"), ("A", "C"))
        assert g.has_cycle() is True
        g.remove_node("C")
        assert g.has_cycle() is False


# ---------------------------------------------------------------------------
# 8. build_from_formulas
# ---------------------------------------------------------------------------

class TestBuildFromFormulas:
    def _mock_refs(self, formula: str) -> List[str]:
        """
        Toy reference extractor: returns all uppercase tokens (A–Z) found
        between brackets like [A] in the formula string.
        """
        import re
        return re.findall(r"\[([A-Za-z0-9_]+)\]", formula)

    def test_simple_linear(self):
        formulas = {
            "A": "100",
            "B": "[A] * 2",
            "C": "[B] + 10",
        }
        g = DependencyGraph()
        g.build_from_formulas(formulas, self._mock_refs)
        assert g.get_dependencies("B") == {"A"}
        assert g.get_dependencies("C") == {"B"}
        order = g.get_calculation_order()
        assert valid_topo_order(order, g)

    def test_references_to_unknown_nodes_ignored(self):
        """References to nodes not in the formula dict are not added."""
        formulas = {
            "A": "[EXTERNAL] + 1",
        }
        g = DependencyGraph()
        g.build_from_formulas(formulas, self._mock_refs)
        # EXTERNAL is not in formulas, so no edge added
        assert g.get_dependencies("A") == set()

    def test_isolated_node_registered(self):
        formulas = {"A": "42", "B": "99"}
        g = DependencyGraph()
        g.build_from_formulas(formulas, self._mock_refs)
        assert "A" in g._nodes
        assert "B" in g._nodes

    def test_build_detects_cycle(self):
        formulas = {
            "A": "[B] + 1",
            "B": "[A] * 2",
        }
        g = DependencyGraph()
        g.build_from_formulas(formulas, self._mock_refs)
        assert g.has_cycle() is True

    def test_build_complex_model(self):
        formulas = {
            "Revenue": "100",
            "COGS": "[Revenue] * 0.6",
            "GrossProfit": "[Revenue] - [COGS]",
            "Opex": "20",
            "EBIT": "[GrossProfit] - [Opex]",
        }
        g = DependencyGraph()
        g.build_from_formulas(formulas, self._mock_refs)
        order = g.get_calculation_order()
        assert valid_topo_order(order, g)
        assert order.index("Revenue") < order.index("COGS")
        assert order.index("COGS") < order.index("GrossProfit")
        assert order.index("GrossProfit") < order.index("EBIT")


# ---------------------------------------------------------------------------
# 9. Multiple disconnected components
# ---------------------------------------------------------------------------

class TestDisconnectedComponents:
    def test_two_chains_independently_sorted(self):
        # Chain 1: A -> B -> C
        # Chain 2: X -> Y -> Z
        g = make_graph(("B", "A"), ("C", "B"), ("Y", "X"), ("Z", "Y"))
        order = g.get_calculation_order()
        assert set(order) == {"A", "B", "C", "X", "Y", "Z"}
        assert valid_topo_order(order, g)

    def test_recalc_only_affects_one_component(self):
        g = make_graph(("B", "A"), ("C", "B"), ("Y", "X"), ("Z", "Y"))
        order = g.get_recalc_order({"A"})
        # Only chain 1 is affected
        assert set(order) == {"A", "B", "C"}
        assert "X" not in order
        assert "Y" not in order
        assert "Z" not in order


# ---------------------------------------------------------------------------
# 10. Large graph stress test
# ---------------------------------------------------------------------------

class TestLargeGraph:
    def test_100_node_linear_chain_order(self):
        """Linear chain: node_0 <- node_1 <- ... <- node_99"""
        g = DependencyGraph()
        nodes = [f"node_{i}" for i in range(100)]
        for i in range(1, 100):
            g.add_dependency(nodes[i], nodes[i - 1])

        order = g.get_calculation_order()
        assert len(order) == 100
        assert valid_topo_order(order, g)
        # node_0 has no dependencies so it must be first; all 100 nodes present
        assert order[0] == "node_0"
        assert set(order) == set(nodes)

    def test_100_node_fan_out_then_in(self):
        """
        root -> leaf_0, root -> leaf_1, ..., root -> leaf_98
        All leaves -> sink
        """
        g = DependencyGraph()
        g.add_node("root")
        g.add_node("sink")
        for i in range(99):
            leaf = f"leaf_{i}"
            g.add_dependency(leaf, "root")
            g.add_dependency("sink", leaf)

        order = g.get_calculation_order()
        assert len(order) == 101  # root + 99 leaves + sink
        assert valid_topo_order(order, g)
        assert order[0] == "root"
        assert order[-1] == "sink"

    def test_large_graph_partial_recalc_minimal(self):
        """
        Two independent chains of 50 nodes each.
        Changing a node in chain 1 should not recalc chain 2.
        """
        g = DependencyGraph()
        chain1 = [f"c1_{i}" for i in range(50)]
        chain2 = [f"c2_{i}" for i in range(50)]
        for i in range(1, 50):
            g.add_dependency(chain1[i], chain1[i - 1])
            g.add_dependency(chain2[i], chain2[i - 1])

        changed = {chain1[10]}
        order = g.get_recalc_order(changed)
        # Only chain1[10] through chain1[49] should be recalced
        assert len(order) == 40
        for node in order:
            assert node.startswith("c1_")
        assert valid_topo_order(order, g)
