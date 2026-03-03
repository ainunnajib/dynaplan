"""
Calculation Dependency Graph — F007

Tracks dependencies between line items, supports topological ordering,
partial recalculation, and circular dependency detection.

Pure Python — no database, no FastAPI, no external dependencies.
"""

from collections import defaultdict, deque
from typing import Callable, Dict, List, Set


class DependencyGraph:
    """
    Directed acyclic graph (DAG) for tracking formula dependencies between
    line items.

    Edges are stored as:
      _deps[node]     = set of nodes that `node` depends ON  (incoming)
      _dependents[node] = set of nodes that depend ON `node` (outgoing)

    Example: if line item B references line item A in its formula,
      _deps["B"]        = {"A"}
      _dependents["A"]  = {"B"}
    """

    def __init__(self) -> None:
        self._nodes: Set[str] = set()
        # node -> set of nodes it depends on
        self._deps: Dict[str, Set[str]] = defaultdict(set)
        # node -> set of nodes that depend on it
        self._dependents: Dict[str, Set[str]] = defaultdict(set)

    # ------------------------------------------------------------------
    # Mutation
    # ------------------------------------------------------------------

    def add_node(self, node_id: str) -> None:
        """Register a line item node. Safe to call multiple times."""
        self._nodes.add(node_id)
        # Ensure entries exist in both dicts even if no edges yet
        if node_id not in self._deps:
            self._deps[node_id] = set()
        if node_id not in self._dependents:
            self._dependents[node_id] = set()

    def add_dependency(self, node_id: str, depends_on: str) -> None:
        """
        Declare that `node_id` depends on `depends_on`.
        Both nodes are auto-registered if not yet present.
        """
        self.add_node(node_id)
        self.add_node(depends_on)
        self._deps[node_id].add(depends_on)
        self._dependents[depends_on].add(node_id)

    def remove_node(self, node_id: str) -> None:
        """
        Remove a node and all edges that reference it (both directions).
        No-op if the node does not exist.
        """
        if node_id not in self._nodes:
            return

        # Remove outgoing edges: node_id depends on these nodes
        for dep in list(self._deps.get(node_id, set())):
            self._dependents[dep].discard(node_id)

        # Remove incoming edges: these nodes depend on node_id
        for dependent in list(self._dependents.get(node_id, set())):
            self._deps[dependent].discard(node_id)

        # Clean up the dicts
        self._deps.pop(node_id, None)
        self._dependents.pop(node_id, None)
        self._nodes.discard(node_id)

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------

    def get_dependencies(self, node_id: str) -> Set[str]:
        """Return the set of nodes that `node_id` directly depends on."""
        return set(self._deps.get(node_id, set()))

    def get_dependents(self, node_id: str) -> Set[str]:
        """Return the set of nodes that directly depend on `node_id`."""
        return set(self._dependents.get(node_id, set()))

    # ------------------------------------------------------------------
    # Ordering
    # ------------------------------------------------------------------

    def get_calculation_order(self) -> List[str]:
        """
        Topological sort of all nodes.

        Returns nodes in dependency-first order so that when processing
        left-to-right, every dependency is evaluated before the nodes
        that use it.

        Raises ValueError if a cycle is detected (use detect_cycles()
        first if you need the cycle details).
        """
        return self._topological_sort(self._nodes)

    def get_recalc_order(self, changed_nodes: Set[str]) -> List[str]:
        """
        Return the minimal ordered list of nodes that must be recalculated
        when the given nodes have changed.

        Algorithm:
        1. BFS downstream (following _dependents edges) from changed_nodes
           to collect all affected nodes (including the changed nodes
           themselves).
        2. Topological-sort that subset so execution order is correct.
        """
        affected = self._downstream_set(changed_nodes)
        return self._topological_sort(affected)

    # ------------------------------------------------------------------
    # Cycle detection
    # ------------------------------------------------------------------

    def has_cycle(self) -> bool:
        """Quick check: does the graph contain at least one cycle?"""
        return len(self.detect_cycles()) > 0

    def detect_cycles(self) -> List[List[str]]:
        """
        Find all simple cycles in the graph using DFS with path tracking.

        Returns a list of cycles, where each cycle is a list of node IDs
        in the cycle (the first and last element are the same node).
        """
        visited: Set[str] = set()
        cycles: List[List[str]] = []
        # Canonical representations we have already recorded to avoid dups
        recorded: Set[frozenset] = set()

        def dfs(node: str, path: List[str], path_set: Set[str]) -> None:
            visited.add(node)
            path.append(node)
            path_set.add(node)

            for neighbour in self._dependents.get(node, set()):
                if neighbour not in self._nodes:
                    continue
                if neighbour in path_set:
                    # Found a cycle — extract the relevant portion
                    cycle_start = path.index(neighbour)
                    cycle = path[cycle_start:] + [neighbour]
                    key = frozenset(cycle[:-1])  # deduplicate
                    if key not in recorded:
                        recorded.add(key)
                        cycles.append(cycle)
                elif neighbour not in visited:
                    dfs(neighbour, path, path_set)

            path.pop()
            path_set.discard(node)

        for node in list(self._nodes):
            if node not in visited:
                dfs(node, [], set())

        return cycles

    # ------------------------------------------------------------------
    # Factory / builder
    # ------------------------------------------------------------------

    def build_from_formulas(
        self,
        formulas: Dict[str, str],
        get_references: Callable[[str], List[str]],
    ) -> None:
        """
        Populate the graph from a dict of {line_item_id: formula_text}.

        `get_references(formula_text)` must return a list of line_item_ids
        that the formula references.

        All line items in `formulas` are registered as nodes.  Edges are
        added for every reference found by `get_references`.
        """
        # Register all known nodes first so isolated nodes are included
        for node_id in formulas:
            self.add_node(node_id)

        for node_id, formula_text in formulas.items():
            refs = get_references(formula_text)
            for ref in refs:
                # Only create edges to nodes that are actually in the model
                if ref in formulas:
                    self.add_dependency(node_id, ref)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _topological_sort(self, nodes: Set[str]) -> List[str]:
        """
        Kahn's algorithm (BFS-based topological sort) over a subset of
        nodes.

        Returns nodes in dependency-first order.
        Raises ValueError on cycle detection within the subset.
        """
        # Build in-degree count restricted to the given node subset
        in_degree: Dict[str, int] = {n: 0 for n in nodes}

        for node in nodes:
            for dep in self._deps.get(node, set()):
                if dep in nodes:
                    in_degree[node] += 1

        # Start with nodes that have no (in-subset) dependencies
        queue: deque = deque(
            sorted(n for n, deg in in_degree.items() if deg == 0)
        )
        result: List[str] = []

        while queue:
            node = queue.popleft()
            result.append(node)

            # Reduce in-degree for downstream nodes within our subset
            for dependent in sorted(self._dependents.get(node, set())):
                if dependent in nodes:
                    in_degree[dependent] -= 1
                    if in_degree[dependent] == 0:
                        queue.append(dependent)

        if len(result) != len(nodes):
            raise ValueError(
                "Cycle detected: cannot produce a valid topological order. "
                "Call detect_cycles() for details."
            )

        return result

    def _downstream_set(self, start_nodes: Set[str]) -> Set[str]:
        """
        BFS from `start_nodes` following _dependents (downstream) edges.
        Returns all reachable nodes including the start nodes themselves.
        """
        visited: Set[str] = set()
        queue: deque = deque()

        for node in start_nodes:
            if node in self._nodes:
                queue.append(node)
                visited.add(node)

        while queue:
            node = queue.popleft()
            for dependent in self._dependents.get(node, set()):
                if dependent not in visited and dependent in self._nodes:
                    visited.add(dependent)
                    queue.append(dependent)

        return visited
