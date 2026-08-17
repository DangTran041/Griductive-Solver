"""
logic/dpll.py
--------------
Bộ giải DPLL SAT Solver hoàn chỉnh.
Bao gồm: Unit Propagation, Conflict Detection, Backtracking, và ghi nhận metrics thực nghiệm (cộng dồn).
"""

import time
import copy
from typing import List, Dict, Tuple, Optional

Clause = List[int]
CNF = List[Clause]
Assignment = Dict[int, bool]


class DPLLSolver:
    def __init__(self):
        # Không reset trong solve() để cộng dồn cho toàn bộ vòng đời của Solver (một màn chơi)
        self.decisions = 0
        self.propagations = 0
        self.backtracks = 0
        self.sat_calls = 0       # Thêm biến đếm số lần gọi SAT theo yêu cầu 4.5
        self.runtime = 0.0

    def solve(self, cnf_clauses: CNF, primary_vars: Optional[List[int]] = None) -> Tuple[bool, Assignment]:
        """
        Khởi tạo và giải bài toán SAT bằng DPLL.
        Trả về (is_sat, assignment_dict).
        """
        self.sat_calls += 1      # Tăng biến đếm mỗi khi gọi
        start_time = time.time()
        
        # Deepcopy để không ảnh hưởng dữ liệu gốc
        working_clauses = copy.deepcopy(cnf_clauses)
        is_sat, model = self._dpll(working_clauses, {})
        
        self.runtime += (time.time() - start_time)  # Cộng dồn thời gian chạy
        return is_sat, model

    def _unit_propagation(self, clauses: CNF, assignment: Assignment) -> Tuple[Optional[CNF], Assignment]:
        """
        Tìm kiếm các mệnh đề đơn vị (Unit Clause) và lan truyền giá trị.
        Trả về (clauses_đã_rút_gọn, assignment_mới).
        Nếu phát hiện mâu thuẫn -> trả về (None, assignment).
        """
        new_clauses = copy.deepcopy(clauses)
        new_assignment = copy.deepcopy(assignment)

        while True:
            unit = None
            for c in new_clauses:
                if len(c) == 1:
                    unit = c[0]
                    break

            if unit is None:
                break

            self.propagations += 1
            var = abs(unit)
            val = (unit > 0)

            if var in new_assignment and new_assignment[var] != val:
                return None, new_assignment

            new_assignment[var] = val

            simplified_clauses = []
            for clause in new_clauses:
                if unit in clause:
                    continue
                neg_unit = -unit
                if neg_unit in clause:
                    new_c = [l for l in clause if l != neg_unit]
                    if len(new_c) == 0:
                        return None, new_assignment
                    simplified_clauses.append(new_c)
                else:
                    simplified_clauses.append(clause)

            new_clauses = simplified_clauses

        return new_clauses, new_assignment

    def _dpll(self, clauses: CNF, assignment: Assignment) -> Tuple[bool, Assignment]:
        """
        Vòng lặp đệ quy cốt lõi của DPLL.
        """
        simplified_clauses, assignment = self._unit_propagation(clauses, assignment)
        
        if simplified_clauses is None:
            return False, {}

        if len(simplified_clauses) == 0:
            return True, assignment

        unassigned_var = None
        for c in simplified_clauses:
            for lit in c:
                v = abs(lit)
                if v not in assignment:
                    unassigned_var = v
                    break
            if unassigned_var is not None:
                break

        if unassigned_var is None:
            return True, assignment

        self.decisions += 1
        branch_true_clauses = copy.deepcopy(simplified_clauses) + [[unassigned_var]]
        is_sat, model = self._dpll(branch_true_clauses, copy.deepcopy(assignment))
        if is_sat:
            return True, model

        self.backtracks += 1
        self.decisions += 1
        branch_false_clauses = copy.deepcopy(simplified_clauses) + [[-unassigned_var]]
        is_sat, model = self._dpll(branch_false_clauses, copy.deepcopy(assignment))
        if is_sat:
            return True, model

        return False, {}