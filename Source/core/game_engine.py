"""
core/game_engine.py
--------------------
Game Engine cho Griductive — KHÔNG import Ursina hay bất kỳ thư viện GUI nào.
Đây là quy tắc bắt buộc theo đề (mục 4.1): Game Engine và GUI phải tách biệt,
để Logic Agent (Phong) có thể test độc lập mà không cần dựng cửa sổ game.

Engine giữ:
  - self.solution        : PRIVATE — đáp án thật của mọi ô. GUI/Agent không
                            bao giờ được đọc trực tiếp field này.
  - self.clues            : toàn bộ clue (kể cả clue của ô chưa lật)
  - self.public_kb         : PUBLIC — chỉ chứa ô đã lật + verdict đã chứng minh.
                            Đây là thứ duy nhất Logic Agent được phép đọc.
"""

import json
from pathlib import Path


class Clue:
    def __init__(self, clue_type, target_cells, k=None, value=None, description=""):
        self.clue_type = clue_type       # FACT / SAME / DIFFERENT / EXACTLY / AT_LEAST / AT_MOST
        self.target_cells = target_cells  # list[(row, col)] — vùng clue tham chiếu tới
        self.k = k                        # dùng cho EXACTLY/AT_LEAST/AT_MOST
        self.value = value                # dùng cho FACT (CRIMINAL/INNOCENT)
        self.description = description


class GameEngine:
    def __init__(self, grid_size=3):
        self.grid_size = grid_size
        self.characters = {}         # (row, col) -> {"name": str, "prof": str}
        self.solution = {}           # (row, col) -> "CRIMINAL"/"INNOCENT"  [PRIVATE]
        self.clues = {}              # (row, col) -> Clue
        self.initial_revealed = []   # list[(row, col)]
        self.public_kb = {}          # (row, col) -> "CRIMINAL"/"INNOCENT"  [PUBLIC]
        self.source_path = None      # ghi lại puzzle nào đang được load (để debug/hiển thị)

    # ------------------------------------------------------------------
    # LOAD — đọc puzzle từ file JSON theo docs/puzzle_format.md
    # ------------------------------------------------------------------
    @classmethod
    def from_json(cls, path):
        path = Path(path)
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)

        engine = cls(grid_size=data["grid_size"])
        engine.source_path = str(path)

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
        engine.restart()  # thiết lập public_kb ban đầu
        return engine

    def _resolve_region(self, region, id_to_pos):
        """Chuyển 1 region (row/column/neighbors/explicit) thành list toạ độ (row, col)."""
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

    # ------------------------------------------------------------------
    # RESTART — chơi lại puzzle hiện tại từ đầu, KHÔNG đổi puzzle
    # ------------------------------------------------------------------
    def restart(self):
        self.public_kb = {}
        for pos in self.initial_revealed:
            self.public_kb[pos] = self.solution[pos]

    # ------------------------------------------------------------------
    # SUBMIT VERDICT
    # ------------------------------------------------------------------
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

    def _check_forced_status(self, pos):
        """
        *** STUB TẠM THỜI ***
        Đây CHƯA phải Logic Agent thật — chỉ xử lý được clue loại FACT trỏ
        trực tiếp tới ô đang xét, để Load/Restart/GUI chạy demo được trong
        lúc chờ Minh (CNF Encoder) + Phong (DPLL Solver + Logic Agent) code xong.

        Khi Phong xong logic/logic_agent.py, THAY TOÀN BỘ hàm này bằng:
            from logic.logic_agent import LogicAgent
            agent = LogicAgent(self.public_kb, self.clues)  # KHÔNG truyền self.solution
            return agent.classify(pos)   # trả "CRIMINAL" / "INNOCENT" / None (UNKNOWN)
        """
        for revealed_pos in list(self.public_kb.keys()):
            clue = self.clues.get(revealed_pos)
            if clue is None:
                continue
            if clue.clue_type == "FACT" and pos in clue.target_cells:
                return clue.value
        return None

    def _pos_label(self, pos):
        r, c = pos
        return f"{chr(ord('A') + c)}{r + 1}"

    # ------------------------------------------------------------------
    # PUBLIC KB — dùng cho Logic Agent / Experiments, không lộ solution
    # ------------------------------------------------------------------
    def get_public_view(self):
        """Trả về đúng những gì Logic Agent được phép thấy — không có 'solution'."""
        return {
            "grid_size": self.grid_size,
            "revealed": dict(self.public_kb),
            "revealed_clues": {
                pos: self.clues[pos] for pos in self.public_kb if pos in self.clues
            },
        }
