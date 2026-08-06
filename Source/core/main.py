from ursina import *

class Clue:
    def __init__(self, clue_type, target_cells, count=None, description=""):
        self.clue_type = clue_type     
        self.target_cells = target_cells 
        self.count = count             
        self.description = description 

class GameEngine:
    def __init__(self, grid_size=3):
        self.grid_size = grid_size
        
        self.secret_data = {
            (0, 0): {"name": "Abel", "prof": "Guard", "status": "INNOCENT", "clue": Clue("EXACTLY", [(0, 0), (0, 1), (0, 2)], count=0, description="No Criminal in Row 1")},
            (0, 1): {"name": "Bea", "prof": "Cook", "status": "INNOCENT", "clue": Clue("FACT", [(1, 0)], description="A2 is Criminal")},
            (0, 2): {"name": "Clara", "prof": "Farmer", "status": "INNOCENT", "clue": Clue("EXACTLY", [(1, 0), (1, 1), (1, 2)], count=2, description="Exactly 2 Criminals in Row 2")},
            (1, 0): {"name": "Derek", "prof": "Clerk", "status": "CRIMINAL", "clue": Clue("FACT", [(1, 1)], description="B2 is Innocent")},
            (1, 1): {"name": "Eliza", "prof": "Detective", "status": "INNOCENT", "clue": Clue("FACT", [(1, 2)], description="C2 is Criminal")},
            (1, 2): {"name": "Franz", "prof": "Guard", "status": "CRIMINAL", "clue": Clue("FACT", [(2, 0)], description="A3 is Innocent")},
            (2, 0): {"name": "Grant", "prof": "Doctor", "status": "INNOCENT", "clue": Clue("FACT", [(2, 1)], description="B3 is Criminal")},
            (2, 1): {"name": "Hannah", "prof": "Artist", "status": "CRIMINAL", "clue": Clue("FACT", [(2, 2)], description="C3 is Innocent")},
            (2, 2): {"name": "Ivy", "prof": "Pilot", "status": "INNOCENT", "clue": Clue("FACT", [(2, 2)], description="All Criminals Found!")},
        }

        self.public_kb = {}
        self.public_kb[(0, 0)] = self.secret_data[(0, 0)]["status"]

    def submit_verdict(self, pos, guessed_status):
        if pos in self.public_kb:
            return "ALREADY_REVEALED", "Ô này đã được lật rồi"

        provable_cells = [(0, 1), (0, 2)]
        
        if pos not in provable_cells and len(self.public_kb) == 1:
            return "NOT_PROVABLE", f"LỖI (NOT_PROVABLE):\nChưa đủ dữ kiện để chứng minh ô {chr(65+pos[1])}{pos[0]+1}.\nBạn đang đoán mò!"

        real_status = self.secret_data[pos]["status"]

        if guessed_status != real_status:
            return "CONTRADICTED", f"LỖI (CONTRADICTED):\nMâu thuẫn! Clue A1 ép buộc ô này phải là {real_status}."

        self.public_kb[pos] = real_status
        return "ACCEPTED", f"CHÍNH XÁC!\n{self.secret_data[pos]['name']} là {real_status}."

class CardEntity(Button):
    def __init__(self, row, col, engine: GameEngine, on_click_callback):
        x_pos = -5.0 + col * 1.7
        y_pos = 2.0 - row * 2.0

        super().__init__(
            parent=scene,
            position=(x_pos, y_pos, 0),
            scale=(1.5, 1.8),
            color=color.light_gray,
            highlight_color=color.cyan
        )

        self.row = row
        self.col = col
        self.engine = engine
        self.on_click_callback = on_click_callback
        
        self.is_selected = False
        self.is_highlighted_by_clue = False

        col_letter = chr(ord('A') + col)
        self.coord_str = f"{col_letter}{row + 1}"

        info = engine.secret_data[(row, col)]
        self.char_name = info["name"]
        self.prof = info["prof"]
        self.clue_obj = info["clue"]

        self.info_text = Text(
            text="",
            parent=self,
            origin=(0, 0),
            position=(0, 0, -0.1),
            scale=2.0,
            color=color.black
        )
        self.update_visual()

    def update_visual(self):
        pos = (self.row, self.col)

        if pos in self.engine.public_kb:
            status = self.engine.public_kb[pos]
            if self.is_highlighted_by_clue:
                self.color = color.magenta
            else:
                self.color = color.lime if status == "INNOCENT" else color.orange
            self.info_text.text = f"[{self.coord_str}]\n{self.char_name}\n({self.prof})\n\n[{status}]\n{self.clue_obj.description}"
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

app = Ursina()

camera.orthographic = True
camera.fov = 7.5

engine = GameEngine()
cards_dict = {}
selected_card = None

console_border = Entity(
    parent=camera.ui,
    model='quad',
    color=color.light_gray,     
    scale=(0.535, 0.295),       
    position=(0.45, 0.22)
)

console_box = Entity(
    parent=console_border,
    model='quad',
    color=color.dark_gray,
    scale=(0.97, 0.95),         
    position=(0, 0, -0.01)      
)

console_title = Text(
    text="[ BẢNG THÔNG BÁO ]", 
    parent=console_box, 
    position=(-0.45, 0.38), 
    scale=0.9, 
    color=color.yellow
)

console_text = Text(
    text="Click bài úp: Chọn ô đoán.\nClick bài ngửa: Xem Clue của ô đó.", 
    parent=console_box, 
    position=(-0.45, 0.15), 
    scale=0.8, 
    color=color.white
)

def log_message(msg, status_type="INFO"):
    console_text.text = msg
    if status_type == "ACCEPTED":
        console_box.color = color.green          
    elif status_type == "NOT_PROVABLE":
        console_box.color = color.yellow         
    elif status_type == "CONTRADICTED":
        console_box.color = color.red           
    else:
        console_box.color = color.dark_gray     

def clear_all_highlights():
    global selected_card
    if selected_card:
        selected_card.is_selected = False

    for card in cards_dict.values():
        card.is_highlighted_by_clue = False
        card.update_visual()

def handle_card_click(card_entity):
    global selected_card
    clear_all_highlights()

    pos = (card_entity.row, card_entity.col)

    if pos in engine.public_kb:
        clue = card_entity.clue_obj
        log_message(f"CLUE [{card_entity.coord_str}]: {clue.description}\nLoại: {clue.clue_type}", "INFO")
        
        for target_pos in clue.target_cells:
            if target_pos in cards_dict:
                cards_dict[target_pos].is_highlighted_by_clue = True
                cards_dict[target_pos].update_visual()
    else:
        selected_card = card_entity
        selected_card.is_selected = True
        selected_card.update_visual()
        log_message(f"Đã chọn ô úp: {card_entity.coord_str} ({card_entity.char_name})\nHãy chọn CRIMINAL hoặc INNOCENT.", "INFO")

def handle_verdict(guessed_status):
    global selected_card
    if not selected_card:
        log_message("Click chọn 1 ô úp trên lưới!", "NOT_PROVABLE")
        return

    pos = (selected_card.row, selected_card.col)
    res_code, msg = engine.submit_verdict(pos, guessed_status)

    log_message(msg, res_code)
    
    if res_code == "ACCEPTED":
        clear_all_highlights()

for r in range(engine.grid_size):
    for c in range(engine.grid_size):
        card = CardEntity(r, c, engine, handle_card_click)
        cards_dict[(r, c)] = card

btn_w, btn_h = 0.24, 0.075
btn_criminal = Button(text='CRIMINAL', color=color.orange, scale=(btn_w, btn_h), position=(0.32, -0.02), parent=camera.ui, on_click=lambda: handle_verdict("CRIMINAL"))
btn_innocent = Button(text='INNOCENT', color=color.lime, scale=(btn_w, btn_h), position=(0.58, -0.02), parent=camera.ui, on_click=lambda: handle_verdict("INNOCENT"))

btn_hint = Button(text='Hint', color=color.azure, scale=(btn_w, btn_h), position=(0.32, -0.12), parent=camera.ui, on_click=lambda: log_message("Hint: Ô B1 hoặc C1 có thể chứng minh!", "INFO"))
btn_auto = Button(text='Auto Solve', color=color.violet, scale=(btn_w, btn_h), position=(0.58, -0.12), parent=camera.ui, on_click=lambda: log_message("Auto Solve: Đang chờ SAT Agent...", "INFO"))

btn_load = Button(text='Load Map', color=color.gray, scale=(btn_w, btn_h), position=(0.32, -0.22), parent=camera.ui, on_click=lambda: log_message("Đã nạp bản đồ mới.", "INFO"))
btn_restart = Button(text='Restart', color=color.red, scale=(btn_w, btn_h), position=(0.58, -0.22), parent=camera.ui, on_click=lambda: log_message("Đã khởi động lại.", "INFO"))

app.run()