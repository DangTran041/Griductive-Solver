"""
core/game_engine.py
--------------------
Game Engine cho Griductive.
Tích hợp LogicAgent và CNFEncoder để thực hiện suy luận logic chính xác,
lưu trữ deduction trace chuẩn theo yêu cầu đồ án.

QUY TẮC TÁCH BẠCH (mục 4.1 đề bài): mọi lời gọi tới CNFEncoder/LogicAgent
CHỈ được truyền dữ liệu qua self._public_view() — dữ liệu này đã lọc bỏ
hoàn toàn 'solution'. TUYỆT ĐỐI KHÔNG truyền self.raw_puzzle_data thẳng
vào CNFEncoder/LogicAgent ở bất kỳ đâu, vì nó chứa đáp án thật.
"""

import json
from pathlib import Path
from logic.cnf_encoder import CNFEncoder, _parse_cell_id
from logic.agent import LogicAgent
from logic.dpll import DPLLSolver


class Clue:
    def __init__(self, clue_type, target_cells, k=None, value=None, description=""):
        self.clue_type = clue_type       # FACT / SAME / DIFFERENT / EXACTLY / AT_LEAST / AT_MOST
        self.target_cells = target_cells  # list[(row, col)]
        self.k = k                        # dùng cho EXACTLY/AT_LEAST/AT_MOST
        self.value = value                # dùng cho FACT (CRIMINAL/INNOCENT)
        self.description = description


class GameEngine:
    def __init__(self, grid_size=3):
        self.grid_size = grid_size
        self.characters = {}         # (row, col) -> {"name": str, "prof": str}
        self.solution = {}           # (row, col) -> "CRIMINAL"/"INNOCENT" [PRIVATE]
        self.clues = {}              # (row, col) -> Clue
        self.initial_revealed = []   # list[(row, col)]
        self.public_kb = {}          # (row, col) -> "CRIMINAL"/"INNOCENT" [PUBLIC]
        self.source_path = None
        self.raw_puzzle_data = None  # Dữ liệu thô ĐẦY ĐỦ (CÓ 'solution') — CHỈ Engine
                                      # dùng nội bộ để load. KHÔNG BAO GIỜ truyền thẳng
                                      # object này cho CNFEncoder/LogicAgent — dùng
                                      # self._public_puzzle() ở mọi nơi khác thay thế.
        self.agent = None            # Sẽ được khởi tạo trong restart()

    @classmethod
    def from_json(cls, path):
        path = Path(path)
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)

        engine = cls(grid_size=data["grid_size"])
        engine.source_path = str(path)
        engine.raw_puzzle_data = data

        id_to_pos = {}
        for ch in data["characters"]:
            pos = (ch["row"], ch["col"])
            id_to_pos[ch["id"]] = pos
            engine.characters[pos] = {"name": ch["name"], "prof": ch["profession"]}

        engine.solution = {
            id_to_pos[cid]: status for cid, status in data["solution"].items()
        }

        for cid, clue_data in data["clues"].items():
            pos = id_to_pos[cid]
            target_cells = engine._resolve_region(clue_data["region"], id_to_pos)
            engine.clues[pos] = Clue(
                clue_type=clue_data["type"],
                target_cells=target_cells,
                k=clue_data.get("k"),
                value=clue_data.get("value"),
                description=clue_data.get("description", ""),
            )

        engine.initial_revealed = [id_to_pos[cid] for cid in data["initial_revealed"]]
        engine.restart()
        return engine

    def _resolve_region(self, region, id_to_pos):
        kind = region["kind"]
        if kind == "row":
            r = region["row"]
            return [(r, c) for c in range(self.grid_size)]
        if kind == "column":
            c = region["col"]
            return [(r, c) for r in range(self.grid_size)]
        if kind == "neighbors":
            r, c = id_to_pos[region["of"]]
            cells = []
            for dr in (-1, 0, 1):
                for dc in (-1, 0, 1):
                    if dr == 0 and dc == 0:
                        continue
                    nr, nc = r + dr, c + dc
                    if 0 <= nr < self.grid_size and 0 <= nc < self.grid_size:
                        cells.append((nr, nc))
            return cells
        if kind == "explicit":
            return [id_to_pos[cid] for cid in region["cells"]]
        raise ValueError(f"Unknown region kind: {kind}")

    def restart(self):
        self.public_kb = {}
        for pos in self.initial_revealed:
            self.public_kb[pos] = self.solution[pos]
        # Agent cố định cho cả vòng chơi — để solver cộng dồn số liệu đúng
        # (decisions/propagations/backtracks/sat_calls) suốt toàn bộ session.
        self.agent = LogicAgent()

    def _pos_label(self, pos):
        r, c = pos
        return f"{chr(ord('A') + c)}{r + 1}"

    def _cid_to_pos(self, cid):
        return _parse_cell_id(cid)

    # ------------------------------------------------------------------
    # NGUỒN DỮ LIỆU DUY NHẤT được phép đưa cho CNFEncoder / LogicAgent.
    # Lọc bỏ hoàn toàn 'solution' — không có cách nào Encoder/Agent với
    # tới được đáp án thật thông qua hàm này.
    # ------------------------------------------------------------------
    def _public_puzzle(self):
        return {
            "grid_size": self.raw_puzzle_data["grid_size"],
            "characters": self.raw_puzzle_data["characters"],
            "clues": self.raw_puzzle_data["clues"],
            # cố ý KHÔNG có "solution"
        }

    def _build_cnf_and_vars(self):
        encoder = CNFEncoder(self._public_puzzle())

        revealed_ids = [self._pos_label(pos) for pos in self.public_kb.keys()]
        known_statuses = {self._pos_label(pos): status for pos, status in self.public_kb.items()}

        public_clues = self._public_puzzle()["clues"]
        cnf, stats = encoder.encode(public_clues, revealed_ids, known_statuses)

        var_map = stats["var_map"]
        rev_var_map = {v: k for k, v in var_map.items()}

        return encoder, cnf, stats, var_map, rev_var_map

    def _check_forced_status(self, pos):
        encoder, cnf, stats, var_map, rev_var_map = self._build_cnf_and_vars()
        target_cid = self._pos_label(pos)

        if target_cid not in var_map:
            return None

        var_id = var_map[target_cid]
        verdict = self.agent.evaluate_cell(var_id, cnf)

        if verdict in ["CRIMINAL", "INNOCENT"]:
            return verdict
        return None

    def submit_verdict(self, pos, guessed_status):
        if pos in self.public_kb:
            return "ALREADY_REVEALED", "Ô này đã được lật rồi"

        forced_status = self._check_forced_status(pos)

        if forced_status is None:
            return (
                "NOT_PROVABLE",
                f"LỖI (NOT_PROVABLE):\nChưa đủ dữ kiện để chứng minh ô {self._pos_label(pos)}.\nBạn đang đoán mò!",
            )

        if guessed_status != forced_status:
            return (
                "CONTRADICTED",
                f"LỖI (CONTRADICTED):\nMâu thuẫn! Dữ kiện hiện có ép buộc ô này phải là {forced_status}.",
            )

        self.public_kb[pos] = forced_status
        return "ACCEPTED", f"CHÍNH XÁC!\n{self.characters[pos]['name']} là {forced_status}."

    def get_hint(self):
        encoder, cnf, stats, var_map, rev_var_map = self._build_cnf_and_vars()

        unresolved_vars = []
        for cid, var_id in var_map.items():
            pos = self._cid_to_pos(cid)
            if pos not in self.public_kb:
                unresolved_vars.append(var_id)

        target_var, verdict = self.agent.get_forced_verdict(unresolved_vars, cnf, record_trace=False)

        if target_var is not None and verdict in ["CRIMINAL", "INNOCENT"]:
            target_cid = rev_var_map[target_var]
            target_pos = self._cid_to_pos(target_cid)
            char_info = self.characters.get(target_pos, {})
            char_name = char_info.get("name", target_cid)
            return {
                "has_hint": True,
                "pos": target_pos,
                "cid": target_cid,
                "verdict": verdict,
                "message": f"GỢI Ý: Ô {target_cid} ({char_name}) chắc chắn phải là {verdict}!"
            }

        return {
            "has_hint": False,
            "pos": None,
            "cid": None,
            "verdict": None,
            "message": "GỢI Ý: Hiện chưa thể suy luận chắc chắn thêm ô nào từ các clue đã lật."
        }

    def auto_solve(self):
        solved_count = 0

        while True:
            encoder, cnf, stats, var_map, rev_var_map = self._build_cnf_and_vars()

            active_clues = [self._pos_label(pos) for pos in self.public_kb.keys()]

            unresolved_vars = []
            for cid, var_id in var_map.items():
                pos = self._cid_to_pos(cid)
                if pos not in self.public_kb:
                    unresolved_vars.append(var_id)

            if not unresolved_vars:
                break

            target_var, verdict = self.agent.get_forced_verdict(
                unresolved_vars, cnf, active_clues=active_clues, record_trace=True
            )

            if target_var is not None and verdict in ["CRIMINAL", "INNOCENT"]:
                target_cid = rev_var_map[target_var]
                target_pos = self._cid_to_pos(target_cid)

                self.public_kb[target_pos] = verdict
                solved_count += 1

                new_clue = self.clues.get(target_pos)
                new_clue_desc = new_clue.description if new_clue else "Không có nội dung clue"
                self.agent.update_latest_revealed_clue(f"{target_cid} -> {new_clue_desc}")
            else:
                break

        return solved_count

    def check_uniqueness(self):
        """Kiểm tra bộ clue đầy đủ có dẫn tới đúng 1 lời giải duy nhất không.

        Thuật toán (tối đa 2 SAT calls):
        1. Encode TẤT CẢ clue → CNF (mọi owner đều revealed).
        2. solve() lần 1: UNSAT → INCONSISTENT.
        3. Tạo blocking clause phủ định model 1, thêm vào CNF.
        4. solve() lần 2: UNSAT → UNIQUE, SAT → NOT_UNIQUE.
        """
        encoder = CNFEncoder(self._public_puzzle())
        public_clues = self._public_puzzle()["clues"]
        all_owners = list(public_clues.keys())

        cnf, stats = encoder.encode(public_clues, revealed_ids=all_owners)
        var_map = stats["var_map"]
        num_primary = stats["num_primary_vars"]
        inv_map = {v: k for k, v in var_map.items()}

        solver = DPLLSolver()
        num_sat_calls = 0

        sat1, raw_model1 = solver.solve(cnf)
        num_sat_calls += 1

        if not sat1:
            return {
                "status": "INCONSISTENT",
                "model": None,
                "second_model": None,
                "num_sat_calls": num_sat_calls,
            }

        model1 = {
            inv_map[vi]: "CRIMINAL" if val else "INNOCENT"
            for vi, val in raw_model1.items() if vi in inv_map
        }

        blocking = []
        for vi in range(1, num_primary + 1):
            if vi in raw_model1:
                blocking.append(-vi if raw_model1[vi] else vi)
            else:
                blocking.append(vi)
        cnf.append(blocking)

        sat2, raw_model2 = solver.solve(cnf)
        num_sat_calls += 1

        if not sat2:
            return {
                "status": "UNIQUE",
                "model": model1,
                "second_model": None,
                "num_sat_calls": num_sat_calls,
            }

        model2 = {
            inv_map[vi]: "CRIMINAL" if val else "INNOCENT"
            for vi, val in raw_model2.items() if vi in inv_map
        }

        return {
            "status": "NOT_UNIQUE",
            "model": model1,
            "second_model": model2,
            "num_sat_calls": num_sat_calls,
        }

    def get_public_view(self):
        """Trả về đúng những gì Logic Agent được phép thấy — KHÔNG có 'solution'."""
        return {
            "grid_size": self.grid_size,
            "characters": [
                {"id": self._pos_label(pos), "row": pos[0], "col": pos[1]}
                for pos in self.characters
            ],
            "revealed": {
                self._pos_label(pos): status for pos, status in self.public_kb.items()
            },
            "revealed_clues": {
                self._pos_label(pos): self.clues[pos]
                for pos in self.public_kb
                if pos in self.clues
            },
        }
