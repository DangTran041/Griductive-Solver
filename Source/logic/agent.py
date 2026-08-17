"""
logic/agent.py
--------------
Deductive Logic Agent cho Griductive.
Chịu trách nhiệm phân loại chứng minh bằng phản chứng và ghi log deduction trace chuẩn xác.
"""

from logic.dpll import DPLLSolver
from typing import List, Tuple, Optional, Any, Dict


class LogicAgent:
    def __init__(self):
        self.solver = DPLLSolver()
        self.deduction_trace: List[Dict[str, Any]] = []
        self.step_counter = 0

    def evaluate_cell(self, cell_var: int, current_cnf: List[List[int]]) -> str:
        """Chứng minh thân phận bằng phản chứng."""
        assume_criminal_cnf = current_cnf + [[cell_var]]
        sat_under_criminal, _ = self.solver.solve(assume_criminal_cnf)

        assume_innocent_cnf = current_cnf + [[-cell_var]]
        sat_under_innocent, _ = self.solver.solve(assume_innocent_cnf)

        if not sat_under_innocent and sat_under_criminal:
            return "CRIMINAL"  
        elif not sat_under_criminal and sat_under_innocent:
            return "INNOCENT"  
        elif not sat_under_criminal and not sat_under_innocent:
            return "INCONSISTENT"  
        else:
            return "UNKNOWN"  

    def get_forced_verdict(self, unresolved_vars: List[int], current_cnf: List[List[int]], 
                           active_clues: Optional[List[str]] = None, 
                           record_trace: bool = False) -> Tuple[Optional[int], str]:
        """Duyệt qua các ô chưa mở để tìm ô đầu tiên bị ép buộc (forced verdict)."""
        for var_id in unresolved_vars:
            verdict = self.evaluate_cell(var_id, current_cnf)
            if verdict in ["CRIMINAL", "INNOCENT"]:
                # Chỉ ghi log nếu đang chạy Auto Solve (tránh việc click Hint cũng bị ghi vào trace)
                if record_trace:
                    self.step_counter += 1
                    self.deduction_trace.append({
                        "step": self.step_counter,
                        "target_var": var_id,
                        "verdict": verdict,
                        "active_clues": active_clues or [],      # Lưu danh sách Clue đang dùng
                        "sat_queries": 2,
                        "sat_calls": self.solver.sat_calls,
                        "decisions": self.solver.decisions,
                        "propagations": self.solver.propagations,
                        "backtracks": self.solver.backtracks,
                        "runtime": round(self.solver.runtime, 6),
                        "newly_revealed_clue": None              # Chờ GameEngine điền thông tin sau
                    })
                return var_id, verdict

        return None, "UNKNOWN"

    def update_latest_revealed_clue(self, clue_description: str):
        """Được gọi bởi GameEngine sau khi lật thẻ để ghi nhận clue mới vào trace."""
        if self.deduction_trace:
            self.deduction_trace[-1]["newly_revealed_clue"] = clue_description