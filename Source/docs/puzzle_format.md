# Puzzle File Format (Griductive)

Đây là định dạng file puzzle dùng chung cho cả 3 phần: Game Engine/GUI (Giao),
CNF Encoder (Minh), và Experiments (Đăng). Mỗi puzzle là 1 file `.json` đặt
trong `Source/stages/`.

## Cấu trúc tổng quát

```json
{
  "id": "stage_3x3_01",
  "grid_size": 3,
  "characters": [
    { "id": "A1", "row": 0, "col": 0, "name": "Abel", "profession": "Guard" }
  ],
  "solution": {
    "A1": "INNOCENT"
  },
  "clues": {
    "A1": {
      "type": "EXACTLY",
      "region": { "kind": "row", "row": 0 },
      "k": 0,
      "description": "No Criminal in Row 1"
    }
  },
  "initial_revealed": ["A1"]
}
```

## Giải thích từng phần

- **id**: tên định danh puzzle, trùng tên file (không đuôi `.json`).
- **grid_size**: N của lưới N×N.
- **characters**: danh sách toàn bộ nhân vật trên lưới. `id` là mã ô
  (cột chữ + hàng số, ví dụ `A1`, `C3`), khớp quy ước trong đề bài
  (cột từ trái→phải là A,B,C..., hàng từ trên→dưới là 1,2,3...).
- **solution**: trạng thái thật của MỌI nhân vật (`"CRIMINAL"` hoặc
  `"INNOCENT"`). Đây là dữ liệu **chỉ Game Engine được đọc** — Logic Agent
  tuyệt đối không được truy cập field này.
- **clues**: mỗi nhân vật gắn với đúng 1 clue. `type` là một trong 6 loại
  bắt buộc (`FACT`, `SAME`, `DIFFERENT`, `EXACTLY`, `AT_LEAST`, `AT_MOST`)
  hoặc loại mở rộng do Minh định nghĩa thêm.
- **region**: vùng mà clue tham chiếu tới, 4 dạng theo đề bài:
  - `{"kind": "row", "row": <int>}`
  - `{"kind": "column", "col": <int>}`
  - `{"kind": "neighbors", "of": "<char_id>"}`
  - `{"kind": "explicit", "cells": ["<char_id>", ...]}`
- **initial_revealed**: danh sách các ô mở sẵn từ đầu (face-up).

## Quy ước dùng chung

- `GameEngine.from_json(path)` (Giao cần thêm factory method này) → nạp
  puzzle, giữ `solution` + toàn bộ `clues` là private, chỉ lộ ra
  `initial_revealed` lúc khởi tạo `public_kb`.
- `CNFEncoder.encode(clues: dict, revealed_ids: list)` (Minh) → chỉ nhận
  các clue đã lật, không bao giờ nhận `solution`.
- `experiments/run_experiments.py` (Đăng) → đọc mọi file trong `stages/`,
  chạy pipeline Encoder → Solver → Agent, đo số liệu.

Miễn tất cả 3 phần cùng đọc/ghi theo format này, mỗi người có thể code
độc lập mà không cần chờ nhau xong mới ráp nối được.
