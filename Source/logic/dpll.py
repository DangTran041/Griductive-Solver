import time
import copy

class DPLLSolver:
    def __init__(self):
        # Biến thống kê thực nghiệm (Phục vụ phần ghi report và làm video của Đăng)
        self.decisions = 0
        self.propagations = 0
        self.backtracks = 0
        self.runtime = 0.0

    def solve(self, cnf_clauses, primary_vars=None):
        """
        Phụ trách: Khởi tạo và gọi thuật toán DPLL đệ quy.
        """
        self.decisions = 0
        self.propagations = 0
        self.backtracks = 0
        start_time = time.time()
        
        # Bắt đầu giải với bộ nhớ gán (assignment) trống
        result, model = self._dpll(cnf_clauses, {})
        
        self.runtime = time.time() - start_time
        return result, model

    def _unit_propagation(self, clauses, assignment):
        """
        Phụ trách: Tìm các mệnh đề đơn (Unit Clause) và lan truyền logic để rút gọn CNF.
        """
        new_clauses = copy.deepcopy(clauses)
        unit_clauses = [c for c in new_clauses if len(c) == 1]
        
        while unit_clauses:
            # Lấy literal duy nhất trong mệnh đề đơn đầu tiên
            unit = unit_clauses[0][0]
            self.propagations += 1
            
            # Gán giá trị: Nếu unit > 0 -> True, ngược lại -> False
            assignment[abs(unit)] = (unit > 0)
            
            next_clauses = []
            for clause in new_clauses:
                # 1. Mệnh đề chứa unit literal -> Đã đúng, loại bỏ khỏi danh sách
                if unit in clause:
                    continue
                
                # 2. Mệnh đề chứa phủ định của unit literal -> Xóa literal đó đi
                neg_unit = -unit
                if neg_unit in clause:
                    new_clause = [l for l in clause if l != neg_unit]
                    next_clauses.append(new_clause)
                else:
                    next_clauses.append(clause)
                    
            new_clauses = next_clauses
            # Cập nhật lại danh sách mệnh đề đơn sau khi rút gọn
            unit_clauses = [c for c in new_clauses if len(c) == 1]
            
        return new_clauses, assignment

    def _dpll(self, clauses, assignment):
        """
        Phụ trách: Vòng lặp đệ quy cốt lõi của DPLL (Tìm mâu thuẫn -> Chọn biến -> Rẽ nhánh).
        """
        # Bước 1: Lan truyền Unit
        clauses, assignment = self._unit_propagation(clauses, assignment)
        
        # Bước 2: Conflict Detection (Kiểm tra điều kiện dừng)
        # Nếu không còn mệnh đề nào -> Tất cả đã được thỏa mãn
        if not clauses:
            return True, assignment
        # Nếu xuất hiện mệnh đề rỗng -> Gặp mâu thuẫn (UNSAT)
        if any(len(c) == 0 for c in clauses):
            return False, {}
            
        # Bước 3: Deterministic variable selection (Chọn biến chưa gán)
        unassigned_var = None
        for clause in clauses:
            for literal in clause:
                var = abs(literal)
                if var not in assignment:
                    unassigned_var = var
                    break
            if unassigned_var:
                break
                
        # Bước 4: Rẽ nhánh và Quay lui (Branching & Backtracking)
        self.decisions += 1
        
        # Nhánh 1: Giả sử unassigned_var là TRUE (Thêm mệnh đề [unassigned_var])
        result, model = self._dpll(clauses + [[unassigned_var]], assignment.copy())
        if result:
            return True, model
            
        # Quay lui
        self.backtracks += 1
        self.decisions += 1
        
        # Nhánh 2: Giả sử unassigned_var là FALSE (Thêm mệnh đề [-unassigned_var])
        result, model = self._dpll(clauses + [[-unassigned_var]], assignment.copy())
        if result:
            return True, model
            
        return False, {}