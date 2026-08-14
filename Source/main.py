"""
main.py
-------
GUI (Ursina). Toàn bộ logic thật nằm ở core/game_engine.py — file này
CHỈ vẽ giao diện và gọi engine, không tự chứa dữ liệu puzzle hay luật chơi.

Load: bấm để chuyển sang puzzle KHÁC (đọc từ Source/stages/*.json), dựng lại
      toàn bộ lưới theo puzzle mới.
Restart: bấm để chơi lại đúng puzzle hiện tại từ đầu (không đổi puzzle).
Hint / Auto Solve: còn là placeholder, CHỜ Phong xong logic/logic_agent.py
      rồi nối vào GameEngine._check_forced_status (xem TODO trong core/game_engine.py).
"""

from ursina import *
from pathlib import Path
from core.game_engine import GameEngine

STAGES_DIR = Path(__file__).parent / "stages"
STAGE_FILES = sorted(STAGES_DIR.glob("*.json"))

# Bàn cờ luôn chiếm ĐÚNG 1 vùng cố định, neo ở góc trên-trái, khớp với vị trí
# mà bản gốc 3x3 của Giao từng chạy đúng (không đè lên panel bên phải).
# grid_size lớn hơn chỉ làm spacing/scale mỗi ô NHỎ LẠI, không mở rộng vùng.
BOARD_LEFT = -5.75
BOARD_TOP = 3.4
BOARD_WIDTH = 6.0
BOARD_HEIGHT = 6.5

app = Ursina()
camera.orthographic = True
camera.fov = 7.5  # giữ nguyên giá trị gốc — đã chạy đúng cho layout neo trái này

state = {
    "engine": None,
    "stage_index": 0,
    "cards": {},
    "selected_pos": None,
}


def compute_layout(grid_size):
    """Tính spacing + scale mỗi ô, LUÔN neo trong đúng vùng BOARD_LEFT/TOP cố định."""
    spacing_x = BOARD_WIDTH / grid_size
    spacing_y = BOARD_HEIGHT / grid_size
    origin_x = BOARD_LEFT + spacing_x / 2
    origin_y = BOARD_TOP - spacing_y / 2
    card_scale = (spacing_x * 0.97, spacing_y * 0.97)
    return spacing_x, spacing_y, origin_x, origin_y, card_scale


class CardEntity(Button):
    def __init__(self, pos, engine, on_click_callback, layout):
        row, col = pos
        spacing_x, spacing_y, origin_x, origin_y, card_scale = layout
        x_pos = origin_x + col * spacing_x
        y_pos = origin_y - row * spacing_y

        super().__init__(
            parent=scene,
            position=(x_pos, y_pos, 0),
            scale=card_scale,
            color=color.light_gray,
            highlight_color=color.cyan,
        )

        self.pos_key = pos
        self.engine = engine
        self.on_click_callback = on_click_callback
        self.is_selected = False
        self.is_highlighted_by_clue = False

        info = engine.characters[pos]
        self.char_name = info["name"]
        self.prof = info["prof"]
        self.coord_str = engine._pos_label(pos)

        # Text scale CỐ ĐỊNH so với chính card cha của nó — card đã tự co theo
        # grid_size rồi (xem compute_layout), nên không co thêm text lần 2 nữa,
        # nếu không sẽ bị co kép (card nhỏ x text nhỏ thêm = quá nhỏ để đọc).
        self.info_text = Text(
            text="", parent=self, origin=(0, 0), position=(0, 0, -0.1),
            scale=2.4, color=color.black,
        )
        self.update_visual()

    def update_visual(self):
        clue = self.engine.clues.get(self.pos_key)
        if self.pos_key in self.engine.public_kb:
            status = self.engine.public_kb[self.pos_key]
            if self.is_highlighted_by_clue:
                self.color = color.magenta
            else:
                self.color = color.lime if status == "INNOCENT" else color.orange
            desc = clue.description if clue else ""
            # Lưới nhỏ (3x3): hiện đủ mô tả. Lưới lớn (4x4+): rút gọn trên card,
            # mô tả đầy đủ vẫn hiện trong bảng thông báo khi click vào ô (xem CLUE log).
            if self.engine.grid_size > 3 and len(desc) > 24:
                desc = desc[:21] + "..."
            self.info_text.text = f"[{self.coord_str}]\n{self.char_name}\n({self.prof})\n\n[{status}]\n{desc}"
        else:
            if self.is_selected:
                self.color = color.yellow
            elif self.is_highlighted_by_clue:
                self.color = color.magenta
            else:
                self.color = color.light_gray
            self.info_text.text = f"[{self.coord_str}]\n{self.char_name}\n({self.prof})\n\n[ ÚP / HIDDEN ]"

    def on_click(self):
        self.on_click_callback(self)


def clear_all_highlights():
    if state["selected_pos"] is not None:
        state["cards"][state["selected_pos"]].is_selected = False
    for card in state["cards"].values():
        card.is_highlighted_by_clue = False
        card.update_visual()


def handle_card_click(card_entity):
    clear_all_highlights()
    engine = state["engine"]
    pos = card_entity.pos_key

    if pos in engine.public_kb:
        clue = engine.clues.get(pos)
        if clue:
            log_message(f"CLUE [{card_entity.coord_str}]: {clue.description}\nLoại: {clue.clue_type}", "INFO")
            for target_pos in clue.target_cells:
                if target_pos in state["cards"]:
                    state["cards"][target_pos].is_highlighted_by_clue = True
                    state["cards"][target_pos].update_visual()
    else:
        state["selected_pos"] = pos
        card_entity.is_selected = True
        card_entity.update_visual()
        log_message(f"Đã chọn ô úp: {card_entity.coord_str} ({card_entity.char_name})\nHãy chọn CRIMINAL hoặc INNOCENT.", "INFO")


def handle_verdict(guessed_status):
    engine = state["engine"]
    if state["selected_pos"] is None:
        log_message("Click chọn 1 ô úp trên lưới!", "NOT_PROVABLE")
        return

    pos = state["selected_pos"]
    res_code, msg = engine.submit_verdict(pos, guessed_status)
    log_message(msg, res_code)

    if res_code == "ACCEPTED":
        state["selected_pos"] = None
        clear_all_highlights()
        state["cards"][pos].update_visual()


def build_grid(engine):
    """Xoá lưới cũ (nếu có) và dựng lưới mới theo engine hiện tại."""
    for card in state["cards"].values():
        destroy(card)
    state["cards"] = {}
    state["selected_pos"] = None

    layout = compute_layout(engine.grid_size)
    for r in range(engine.grid_size):
        for c in range(engine.grid_size):
            pos = (r, c)
            card = CardEntity(pos, engine, handle_card_click, layout)
            state["cards"][pos] = card


def load_stage(index):
    """LOAD THẬT: đọc puzzle kế tiếp trong Source/stages/, dựng lại toàn bộ lưới."""
    if not STAGE_FILES:
        log_message("Không tìm thấy puzzle nào trong Source/stages/", "NOT_PROVABLE")
        return

    index = index % len(STAGE_FILES)
    path = STAGE_FILES[index]
    engine = GameEngine.from_json(path)

    state["engine"] = engine
    state["stage_index"] = index
    build_grid(engine)
    log_message(f"Đã nạp puzzle: {path.name} ({engine.grid_size}x{engine.grid_size})", "ACCEPTED")


def handle_load():
    load_stage(state["stage_index"] + 1)


def handle_restart():
    """RESTART THẬT: giữ nguyên puzzle hiện tại, chỉ reset trạng thái đã lật."""
    engine = state["engine"]
    engine.restart()
    for card in state["cards"].values():
        card.is_highlighted_by_clue = False
        card.is_selected = False
        card.update_visual()
    state["selected_pos"] = None
    log_message("Đã khởi động lại puzzle hiện tại.", "INFO")


def handle_hint():
    """Xử lý sự kiện bấm nút Hint: Tìm ô có thể chứng minh được và highlight ô đó."""
    engine = state["engine"]
    hint_data = engine.get_hint()

    if hint_data["has_hint"]:
        pos = hint_data["pos"]
        clear_all_highlights()
        
        # Đánh dấu chọn ô gợi ý trên GUI
        state["selected_pos"] = pos
        if pos in state["cards"]:
            state["cards"][pos].is_selected = True
            state["cards"][pos].update_visual()
            
        log_message(hint_data["message"], "ACCEPTED")
    else:
        log_message(hint_data["message"], "NOT_PROVABLE")


def handle_auto_solve():
    """Xử lý sự kiện bấm nút Auto Solve: Gọi thuật toán tự động giải từng bước."""
    engine = state["engine"]
    clear_all_highlights()

    solved_count = engine.auto_solve()

    # Cập nhật hiển thị toàn bộ bài trên lưới
    for card in state["cards"].values():
        card.update_visual()

    if solved_count > 0:
        log_message(f"AUTO SOLVE: Đã suy luận tự động thành công {solved_count} ô!", "ACCEPTED")
    else:
        log_message("AUTO SOLVE: Không tìm thấy ô nào có thể suy luận thêm từ dữ kiện hiện tại.", "NOT_PROVABLE")


# ---------------- Console UI ----------------
# Dùng Text(background=True) — Ursina tự tạo khung nền vừa khít với chữ,
# tránh lỗi toạ độ lồng nhau (con nằm ngoài khung cha) như cách làm cũ.
console_text = Text(
    text="[ BẢNG THÔNG BÁO ]\nClick bài úp: Chọn ô đoán.\nClick bài ngửa: Xem Clue của ô đó.",
    parent=camera.ui,
    position=(0.18, 0.35),
    scale=1.3,
    color=color.black,
    background=True,
)


def log_message(msg, status_type="INFO"):
    console_text.text = msg
    console_text.background.color = {
        "ACCEPTED": color.green,
        "NOT_PROVABLE": color.yellow,
        "CONTRADICTED": color.red,
        "INFO": color.gray,
    }.get(status_type, color.gray)


# ---------------- Buttons ----------------
btn_w, btn_h = 0.24, 0.075
Button(text='CRIMINAL', color=color.orange, scale=(btn_w, btn_h), position=(0.32, -0.02), parent=camera.ui, on_click=lambda: handle_verdict("CRIMINAL"))
Button(text='INNOCENT', color=color.lime, scale=(btn_w, btn_h), position=(0.58, -0.02), parent=camera.ui, on_click=lambda: handle_verdict("INNOCENT"))
Button(text='Hint', color=color.azure, scale=(btn_w, btn_h), position=(0.32, -0.12), parent=camera.ui, on_click=handle_hint)
Button(text='Auto Solve', color=color.violet, scale=(btn_w, btn_h), position=(0.58, -0.12), parent=camera.ui, on_click=handle_auto_solve)
Button(text='Load Next Map', color=color.gray, scale=(btn_w, btn_h), position=(0.32, -0.22), parent=camera.ui, on_click=handle_load)
Button(text='Restart', color=color.red, scale=(btn_w, btn_h), position=(0.58, -0.22), parent=camera.ui, on_click=handle_restart)

# Nạp puzzle đầu tiên khi khởi động
load_stage(0)

app.run()
