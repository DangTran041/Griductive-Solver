from logic.dpll import DPLLSolver

class LogicAgent:
    def __init__(self):
        self.solver = DPLLSolver()
        self.deduction_trace = [] # Chứa chuỗi hành động để xuất ra report
        self.step_counter = 0

    def evaluate_cell(self, cell_var, current_cnf):
        """
        Phụ trách: Phân loại tính đúng sai của một nhân vật bằng phương pháp phản chứng.
        cell_var: Số nguyên định danh cho nhân vật (Do hàm của Minh cung cấp).
        """
        # Phản chứng 1: Giả sử người này VÔ TỘI (~C_i)
        assume_innocent_cnf = current_cnf + [[-cell_var]]
        is_sat_innocent, _ = self.solver.solve(assume_innocent_cnf)
        
        # Phản chứng 2: Giả sử người này LÀ TỘI PHẠM (C_i)
        assume_criminal_cnf = current_cnf + [[cell_var]]
        is_sat_criminal, _ = self.solver.solve(assume_criminal_cnf)

        # Rút ra kết luận dựa trên luật của đồ án:
        if not is_sat_innocent and is_sat_criminal:
            return "CRIMINAL" # Vô tội là sai -> Chắc chắn là Tội phạm
        elif is_sat_innocent and not is_sat_criminal:
            return "INNOCENT" # Tội phạm là sai -> Chắc chắn Vô tội
        elif not is_sat_innocent and not is_sat_criminal:
            return "INCONSISTENT" # Cơ sở tri thức bị lỗi/mâu thuẫn
        else:
            return "UNKNOWN" # Cả hai đều có khả năng -> Không được đoán

    def get_forced_verdict(self, unresolved_cells, current_cnf):
        """
        Phụ trách: Duyệt qua các ô chưa mở để tìm ra 1 phán quyết "chắc chắn đúng" tiếp theo.
        unresolved_cells: List các biến đại diện cho các thẻ úp (Ví dụ: [1, 2, 4, 5])
        """
        for var_id in unresolved_cells:
            verdict = self.evaluate_cell(var_id, current_cnf)
            
            if verdict in ["CRIMINAL", "INNOCENT"]:
                self.step_counter += 1
                # Ghi nhận log quá trình (Deduction trace)
                trace_log = {
                    "step": self.step_counter,
                    "target_var": var_id,
                    "verdict": verdict,
                    "metrics": {
                        "decisions": self.solver.decisions,
                        "propagations": self.solver.propagations,
                        "runtime": round(self.solver.runtime, 4)
                    }
                }
                self.deduction_trace.append(trace_log)
                
                # Chỉ trả về phán quyết CHẮC CHẮN đầu tiên tìm thấy
                return var_id, verdict
                
        # Nếu duyệt hết mà không có ô nào chắc chắn thì trả về UNKNOWN
        return None, "UNKNOWN"