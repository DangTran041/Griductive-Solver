"""CNF encoder and direct semantic evaluators for Griductive clues."""

from __future__ import annotations

import itertools
from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Mapping, MutableMapping, Optional, Sequence, Tuple

CellId = str
Literal = int
Clause = List[Literal]
CNF = List[Clause]
StatusValue = Any

VALID_CORE_TYPES = {
    "FACT",
    "SAME",
    "DIFFERENT",
    "EXACTLY",
    "AT_LEAST",
    "AT_MOST",
}

# Extension clues implemented in this module.
VALID_EXTENSION_TYPES = {
    "PARITY",        # parity over one region: EVEN / ODD
    "COUNT_COMPARE", # compare criminal counts of two regions
}

VALID_ALL_TYPES = VALID_CORE_TYPES | VALID_EXTENSION_TYPES
DEFAULT_MAX_EXTENSION_ENUM_VARS = 14


@dataclass(frozen=True)
class Cell:
    row: int
    col: int
    cell_id: CellId


def _status_to_bool(value: StatusValue) -> bool:
    """Normalize assignment values to bool where True means CRIMINAL."""
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        v = value.strip().upper()
        if v == "CRIMINAL":
            return True
        if v == "INNOCENT":
            return False
    raise ValueError(f"Unsupported status value: {value!r}")


def _parse_cell_id(cell_id: str) -> Tuple[int, int]:
    """Parse A1-like ids into zero-based (row, col)."""
    if not isinstance(cell_id, str) or len(cell_id) < 2:
        raise ValueError(f"Invalid cell id: {cell_id!r}")

    letters = []
    digits = []
    for ch in cell_id:
        if ch.isalpha() and not digits:
            letters.append(ch.upper())
        elif ch.isdigit():
            digits.append(ch)
        else:
            raise ValueError(f"Invalid cell id: {cell_id!r}")

    if not letters or not digits:
        raise ValueError(f"Invalid cell id: {cell_id!r}")

    col = 0
    for ch in letters:
        col = col * 26 + (ord(ch) - ord("A") + 1)
    col -= 1
    row = int("".join(digits)) - 1

    if row < 0 or col < 0:
        raise ValueError(f"Invalid cell id: {cell_id!r}")
    return row, col


def _require_keys(obj: Mapping[str, Any], required_keys: Sequence[str], context: str) -> None:
    missing = [key for key in required_keys if key not in obj]
    if missing:
        joined = ", ".join(missing)
        raise ValueError(f"Missing required key(s) [{joined}] in {context}")


def evaluate_clue_semantics(
    clue: Mapping[str, Any],
    assignment: Mapping[CellId, StatusValue],
    *,
    resolve_region,
) -> bool:
    """
    Direct semantic evaluator for one clue without CNF conversion.

    Parameters
    ----------
    clue:
        Structured clue object.
    assignment:
        Full assignment over involved cell ids.
    resolve_region:
        Callable that converts one region object to a list of cell ids.
    """
    clue_type = str(clue.get("type", "")).upper()
    if clue_type not in VALID_ALL_TYPES:
        raise ValueError(f"Unsupported clue type: {clue_type}")

    def val(cell_id: CellId) -> bool:
        if cell_id not in assignment:
            raise ValueError(f"Missing assignment for cell {cell_id}")
        return _status_to_bool(assignment[cell_id])

    if clue_type == "FACT":
        _require_keys(clue, ["region", "value"], "FACT clue")
        region_cells = resolve_region(clue["region"])
        if len(region_cells) != 1:
            raise ValueError("FACT expects a region of exactly one cell")
        expected = _status_to_bool(clue["value"])
        return val(region_cells[0]) == expected

    if clue_type == "SAME":
        _require_keys(clue, ["region"], "SAME clue")
        region_cells = resolve_region(clue["region"])
        if len(region_cells) != 2:
            raise ValueError("SAME expects a region of exactly two cells")
        a, b = region_cells
        return val(a) == val(b)

    if clue_type == "DIFFERENT":
        _require_keys(clue, ["region"], "DIFFERENT clue")
        region_cells = resolve_region(clue["region"])
        if len(region_cells) != 2:
            raise ValueError("DIFFERENT expects a region of exactly two cells")
        a, b = region_cells
        return val(a) != val(b)

    if clue_type in {"EXACTLY", "AT_LEAST", "AT_MOST"}:
        _require_keys(clue, ["region", "k"], f"{clue_type} clue")
        region_cells = resolve_region(clue["region"])
        k = int(clue["k"])
        count = sum(1 for cid in region_cells if val(cid))
        if clue_type == "EXACTLY":
            return count == k
        if clue_type == "AT_LEAST":
            return count >= k
        return count <= k

    if clue_type == "PARITY":
        _require_keys(clue, ["region", "parity"], "PARITY clue")
        region_cells = resolve_region(clue["region"])
        parity_value = str(clue["parity"]).upper()
        if parity_value not in {"EVEN", "ODD"}:
            raise ValueError("PARITY clue requires parity in {EVEN, ODD}")
        count = sum(1 for cid in region_cells if val(cid))
        is_even = (count % 2) == 0
        return is_even if parity_value == "EVEN" else (not is_even)

    # COUNT_COMPARE
    _require_keys(clue, ["left_region", "right_region", "op"], "COUNT_COMPARE clue")
    left_cells = resolve_region(clue["left_region"])
    right_cells = resolve_region(clue["right_region"])
    op = str(clue["op"]).strip()
    left = sum(1 for cid in left_cells if val(cid))
    right = sum(1 for cid in right_cells if val(cid))

    if op == ">":
        return left > right
    if op == ">=":
        return left >= right
    if op == "<":
        return left < right
    if op == "<=":
        return left <= right
    if op == "==":
        return left == right
    if op == "!=":
        return left != right
    raise ValueError("COUNT_COMPARE clue requires op in {>, >=, <, <=, ==, !=}")


class CNFEncoder:
    """Reusable Griductive clue-to-CNF encoder with deterministic variable mapping."""

    def __init__(
        self,
        puzzle: Optional[Mapping[str, Any]] = None,
        max_extension_enum_vars: int = DEFAULT_MAX_EXTENSION_ENUM_VARS,
    ):
        self.grid_size: Optional[int] = None
        self.id_to_cell: Dict[CellId, Cell] = {}
        self.pos_to_id: Dict[Tuple[int, int], CellId] = {}
        self.character_ids: List[CellId] = []
        self.max_extension_enum_vars = int(max_extension_enum_vars)
        if self.max_extension_enum_vars < 1:
            raise ValueError("max_extension_enum_vars must be >= 1")

        if puzzle is not None:
            self.configure(puzzle)

    def configure(self, puzzle: Mapping[str, Any]) -> None:
        """Configure board metadata from a puzzle dictionary."""
        if "grid_size" not in puzzle:
            raise ValueError("Puzzle must contain 'grid_size'")
        self.grid_size = int(puzzle["grid_size"])

        cells: Dict[CellId, Cell] = {}
        if "characters" in puzzle and puzzle["characters"]:
            for item in puzzle["characters"]:
                cid = str(item["id"])
                row = int(item["row"])
                col = int(item["col"])
                cells[cid] = Cell(row=row, col=col, cell_id=cid)
        else:
            # Fallback: infer ids from clues if characters list is unavailable.
            inferred_ids = self._collect_ids_from_clues(puzzle.get("clues", {}))
            for cid in inferred_ids:
                row, col = _parse_cell_id(cid)
                cells[cid] = Cell(row=row, col=col, cell_id=cid)

        self.id_to_cell = cells
        self.pos_to_id = {(cell.row, cell.col): cid for cid, cell in cells.items()}
        self.character_ids = self._sorted_ids(cells.keys())

    def encode(
        self,
        clues: Mapping[str, Mapping[str, Any]],
        revealed_ids: Iterable[str],
        known_statuses: Optional[Mapping[str, StatusValue]] = None,
    ) -> Tuple[CNF, Dict[str, Any]]:
        """
        Encode current KB_t to CNF.

        Parameters
        ----------
        clues:
            Full clue map: owner cell id -> structured clue.
        revealed_ids:
            IDs of already-revealed characters. Only those clues are active in KB_t.
        known_statuses:
            Optional proved statuses to be injected as unit clauses.
        """
        self._ensure_metadata(clues)
        var_map = {cid: i + 1 for i, cid in enumerate(self.character_ids)}

        cnf: CNF = []
        per_clue_clause_count: Dict[str, int] = {}

        for owner_id in self._sorted_ids(revealed_ids):
            if owner_id not in clues:
                continue
            clue = clues[owner_id]
            clauses_before = len(cnf)
            clue_clauses = self._encode_clue(clue, var_map)
            cnf.extend(clue_clauses)
            per_clue_clause_count[owner_id] = len(cnf) - clauses_before

        if known_statuses:
            for cid in self._sorted_ids(known_statuses.keys()):
                if cid not in var_map:
                    raise ValueError(f"Unknown cell id in known_statuses: {cid}")
                lit = var_map[cid] if _status_to_bool(known_statuses[cid]) else -var_map[cid]
                cnf.append([lit])

        stats = {
            "num_primary_vars": len(var_map),
            "num_aux_vars": 0,
            "num_vars": len(var_map),
            "num_clauses": len(cnf),
            "var_map": dict(var_map),
            "clauses_per_revealed_clue": per_clue_clause_count,
        }
        return cnf, stats

    def evaluate_clue(
        self,
        clue: Mapping[str, Any],
        assignment: Mapping[CellId, StatusValue],
    ) -> bool:
        """Direct semantic evaluator for one clue (without CNF conversion)."""
        self._ensure_metadata({})
        return evaluate_clue_semantics(clue, assignment, resolve_region=self.resolve_region)

    def evaluate_all(
        self,
        clues: Mapping[str, Mapping[str, Any]],
        assignment: Mapping[CellId, StatusValue],
        revealed_ids: Optional[Iterable[str]] = None,
    ) -> Dict[str, bool]:
        """Direct semantic evaluator for multiple clues."""
        self._ensure_metadata(clues)
        if revealed_ids is None:
            owners = self._sorted_ids(clues.keys())
        else:
            owners = self._sorted_ids(revealed_ids)

        out: Dict[str, bool] = {}
        for owner_id in owners:
            if owner_id in clues:
                out[owner_id] = self.evaluate_clue(clues[owner_id], assignment)
        return out

    # ------------------------------------------------------------------
    # Region resolution
    # ------------------------------------------------------------------
    def resolve_region(self, region: Mapping[str, Any]) -> List[CellId]:
        """Resolve one region object into an ordered list of distinct cell ids."""
        _require_keys(region, ["kind"], "region")
        kind = str(region["kind"]).lower()

        if kind == "row":
            _require_keys(region, ["row"], "row region")
            row = int(region["row"])
            cells = [cid for cid, cell in self.id_to_cell.items() if cell.row == row]
            return self._sorted_ids(cells)

        if kind == "column":
            _require_keys(region, ["col"], "column region")
            col = int(region["col"])
            cells = [cid for cid, cell in self.id_to_cell.items() if cell.col == col]
            return self._sorted_ids(cells)

        if kind == "neighbors":
            _require_keys(region, ["of"], "neighbors region")
            of_id = str(region["of"])
            if of_id not in self.id_to_cell:
                raise ValueError(f"neighbors.of references unknown cell: {of_id}")
            center = self.id_to_cell[of_id]
            found = []
            for dr in (-1, 0, 1):
                for dc in (-1, 0, 1):
                    if dr == 0 and dc == 0:
                        continue
                    pos = (center.row + dr, center.col + dc)
                    neighbor_id = self.pos_to_id.get(pos)
                    if neighbor_id is not None:
                        found.append(neighbor_id)
            return self._sorted_ids(found)

        if kind == "explicit":
            _require_keys(region, ["cells"], "explicit region")
            cells = [str(cid) for cid in region.get("cells", [])]
            self._validate_known_cells(cells)
            return self._sorted_ids(cells)

        # Advanced region extension: intersection of two regions.
        if kind == "intersection":
            _require_keys(region, ["left", "right"], "intersection region")
            left = set(self.resolve_region(region["left"]))
            right = set(self.resolve_region(region["right"]))
            return self._sorted_ids(left.intersection(right))

        # Advanced region extension: board corners.
        if kind == "corners":
            if self.grid_size is None:
                raise ValueError("corners requires configured grid_size")
            corners = [
                self.pos_to_id[(0, 0)],
                self.pos_to_id[(0, self.grid_size - 1)],
                self.pos_to_id[(self.grid_size - 1, 0)],
                self.pos_to_id[(self.grid_size - 1, self.grid_size - 1)],
            ]
            return self._sorted_ids(corners)

        raise ValueError(f"Unknown region kind: {kind}")

    # ------------------------------------------------------------------
    # Internal encode helpers
    # ------------------------------------------------------------------
    def _encode_clue(self, clue: Mapping[str, Any], var_map: Mapping[CellId, int]) -> CNF:
        clue_type = str(clue.get("type", "")).upper()
        if clue_type not in VALID_ALL_TYPES:
            raise ValueError(f"Unsupported clue type: {clue_type}")

        if clue_type == "FACT":
            _require_keys(clue, ["region", "value"], "FACT clue")
            cells = self.resolve_region(clue["region"])
            if len(cells) != 1:
                raise ValueError("FACT expects a region of exactly one cell")
            lit = var_map[cells[0]] if _status_to_bool(clue["value"]) else -var_map[cells[0]]
            return [[lit]]

        if clue_type == "SAME":
            _require_keys(clue, ["region"], "SAME clue")
            cells = self.resolve_region(clue["region"])
            if len(cells) != 2:
                raise ValueError("SAME expects a region of exactly two cells")
            a, b = var_map[cells[0]], var_map[cells[1]]
            return [[a, -b], [-a, b]]

        if clue_type == "DIFFERENT":
            _require_keys(clue, ["region"], "DIFFERENT clue")
            cells = self.resolve_region(clue["region"])
            if len(cells) != 2:
                raise ValueError("DIFFERENT expects a region of exactly two cells")
            a, b = var_map[cells[0]], var_map[cells[1]]
            return [[a, b], [-a, -b]]

        if clue_type in {"EXACTLY", "AT_LEAST", "AT_MOST"}:
            _require_keys(clue, ["region", "k"], f"{clue_type} clue")
            cells = self.resolve_region(clue["region"])
            vars_in_region = [var_map[cid] for cid in cells]
            k = int(clue["k"])
            self._validate_k(k, len(vars_in_region), clue_type)

            if clue_type == "EXACTLY":
                return self._at_most(vars_in_region, k) + self._at_least(vars_in_region, k)
            if clue_type == "AT_LEAST":
                return self._at_least(vars_in_region, k)
            return self._at_most(vars_in_region, k)

        if clue_type == "PARITY":
            _require_keys(clue, ["region", "parity"], "PARITY clue")
            cells = self.resolve_region(clue["region"])
            vars_in_region = [var_map[cid] for cid in cells]
            if len(vars_in_region) > self.max_extension_enum_vars:
                raise ValueError(
                    "PARITY encoding aborted: region size "
                    f"{len(vars_in_region)} exceeds max_extension_enum_vars="
                    f"{self.max_extension_enum_vars}"
                )
            parity = str(clue["parity"]).upper()
            if parity not in {"EVEN", "ODD"}:
                raise ValueError("PARITY clue requires parity in {EVEN, ODD}")
            want_even = parity == "EVEN"

            invalid_assignments = []
            for bits in itertools.product([0, 1], repeat=len(vars_in_region)):
                is_even = (sum(bits) % 2) == 0
                if is_even != want_even:
                    invalid_assignments.append(bits)
            return self._forbid_assignments(vars_in_region, invalid_assignments)

        # COUNT_COMPARE
        _require_keys(clue, ["left_region", "right_region", "op"], "COUNT_COMPARE clue")
        left_cells = self.resolve_region(clue["left_region"])
        right_cells = self.resolve_region(clue["right_region"])
        op = str(clue["op"]).strip()

        all_cells = self._sorted_ids(set(left_cells).union(right_cells))
        if len(all_cells) > self.max_extension_enum_vars:
            raise ValueError(
                "COUNT_COMPARE encoding aborted: union size "
                f"{len(all_cells)} exceeds max_extension_enum_vars="
                f"{self.max_extension_enum_vars}"
            )
        all_vars = [var_map[cid] for cid in all_cells]

        left_set = set(left_cells)
        right_set = set(right_cells)

        invalid_assignments = []
        for bits in itertools.product([0, 1], repeat=len(all_cells)):
            values = {cid: bits[i] for i, cid in enumerate(all_cells)}
            left_count = sum(values[cid] for cid in left_set)
            right_count = sum(values[cid] for cid in right_set)
            if not self._compare_counts(left_count, right_count, op):
                invalid_assignments.append(bits)

        return self._forbid_assignments(all_vars, invalid_assignments)

    @staticmethod
    def _compare_counts(left: int, right: int, op: str) -> bool:
        if op == ">":
            return left > right
        if op == ">=":
            return left >= right
        if op == "<":
            return left < right
        if op == "<=":
            return left <= right
        if op == "==":
            return left == right
        if op == "!=":
            return left != right
        raise ValueError("COUNT_COMPARE clue requires op in {>, >=, <, <=, ==, !=}")

    @staticmethod
    def _forbid_assignments(vars_in_order: Sequence[int], assignments: Iterable[Sequence[int]]) -> CNF:
        """
        Forbid each complete assignment over vars_in_order.

        If one assignment is (x1=1, x2=0, x3=1), its blocking clause is:
            (~x1 OR x2 OR ~x3)
        """
        clauses: CNF = []
        for bits in assignments:
            if len(bits) != len(vars_in_order):
                raise ValueError("Assignment length mismatch")
            clause: Clause = []
            for bit, var in zip(bits, vars_in_order):
                clause.append(-var if bit == 1 else var)
            clauses.append(clause)
        return clauses

    @staticmethod
    def _at_most(vars_in_region: Sequence[int], k: int) -> CNF:
        n = len(vars_in_region)
        if k < 0:
            return [[]]  # immediate UNSAT
        if k >= n:
            return []

        clauses: CNF = []
        for combo in itertools.combinations(vars_in_region, k + 1):
            clauses.append([-v for v in combo])
        return clauses

    @staticmethod
    def _at_least(vars_in_region: Sequence[int], k: int) -> CNF:
        n = len(vars_in_region)
        if k <= 0:
            return []
        if k > n:
            return [[]]  # immediate UNSAT

        clauses: CNF = []
        # At least k true <=> every subset of size (n-k+1) cannot be all false.
        for combo in itertools.combinations(vars_in_region, n - k + 1):
            clauses.append(list(combo))
        return clauses

    @staticmethod
    def _sorted_ids(cell_ids: Iterable[str]) -> List[str]:
        return sorted(set(str(cid) for cid in cell_ids), key=lambda cid: _parse_cell_id(cid))

    @staticmethod
    def _collect_ids_from_clues(clues: Mapping[str, Mapping[str, Any]]) -> List[str]:
        found = set(str(owner) for owner in clues.keys())

        def walk_region(region: Mapping[str, Any]) -> None:
            _require_keys(region, ["kind"], "region")
            kind = str(region.get("kind", "")).lower()
            if kind == "explicit":
                _require_keys(region, ["cells"], "explicit region")
                for cid in region.get("cells", []):
                    found.add(str(cid))
            elif kind == "neighbors":
                _require_keys(region, ["of"], "neighbors region")
                found.add(str(region["of"]))
            elif kind == "intersection":
                _require_keys(region, ["left", "right"], "intersection region")
                walk_region(region["left"])
                walk_region(region["right"])

        for clue in clues.values():
            if not isinstance(clue, Mapping):
                continue
            ctype = str(clue.get("type", "")).upper()
            if "region" in clue:
                walk_region(clue["region"])
            if ctype == "COUNT_COMPARE":
                walk_region(clue["left_region"])
                walk_region(clue["right_region"])

        return CNFEncoder._sorted_ids(found)

    def _ensure_metadata(self, clues: Mapping[str, Mapping[str, Any]]) -> None:
        if self.character_ids:
            return

        inferred_ids = self._collect_ids_from_clues(clues)
        if not inferred_ids:
            raise ValueError("Cannot build variable map: no cells found")

        inferred_cells: Dict[CellId, Cell] = {}
        for cid in inferred_ids:
            row, col = _parse_cell_id(cid)
            inferred_cells[cid] = Cell(row=row, col=col, cell_id=cid)

        self.id_to_cell = inferred_cells
        self.pos_to_id = {(cell.row, cell.col): cid for cid, cell in inferred_cells.items()}
        self.character_ids = self._sorted_ids(inferred_ids)

        if self.grid_size is None:
            max_row = max(cell.row for cell in inferred_cells.values())
            max_col = max(cell.col for cell in inferred_cells.values())
            self.grid_size = max(max_row, max_col) + 1

    def _validate_known_cells(self, cells: Iterable[str]) -> None:
        for cid in cells:
            if cid not in self.id_to_cell:
                raise ValueError(f"Unknown cell id: {cid}")

    @staticmethod
    def _validate_k(k: int, region_size: int, clue_type: str) -> None:
        if k < 0 or k > region_size:
            raise ValueError(f"{clue_type} has invalid k={k} for region size {region_size}")
