"""
run_experiments.py
-------------------
Chạy toàn bộ puzzle trong Source/stages/ qua pipeline
CNF Encoder -> DPLL Solver -> Deductive Logic Agent, thu thập số liệu
theo đúng yêu cầu mục 4.5 của đề bài:
  1. Số biến chính + biến phụ
  2. Số mệnh đề CNF
  3. Số lần gọi SAT
  4. Số decision / propagation / backtrack
  5. Số bước suy diễn (deduction steps / reveal waves)
  6. Thời gian chạy

Cách chạy:
    python experiments/run_experiments.py
    python experiments/run_experiments.py --stages-dir Source/stages --out results.csv

LƯU Ý CHO NHÓM:
Script này được viết TRƯỚC KHI logic/cnf_encoder.py, logic/dpll_solver.py,
logic/logic_agent.py hoàn thiện. Nó import các module đó qua try/except,
và nếu chưa có sẽ tự chạy ở "DRY-RUN MODE" (chỉ load + validate puzzle,
không giải), để không bị treo cứng chờ code người khác xong.

Khi Minh (CNF Encoder), Phong (DPLL + Agent) code xong, chỉ cần đảm bảo
đúng interface bên dưới (phần "EXPECTED INTERFACE") là script này chạy
được ngay, không cần sửa gì thêm.

EXPECTED INTERFACE (thống nhất với Minh + Phong):

    from logic.cnf_encoder import CNFEncoder
    encoder = CNFEncoder()
    cnf, stats = encoder.encode(clues: dict, revealed_ids: list[str])
    # stats phải có: stats["num_vars"], stats["num_aux_vars"], stats["num_clauses"]

    from logic.logic_agent import LogicAgent
    agent = LogicAgent(puzzle)  # puzzle = dữ liệu đã load từ JSON (không gồm 'solution')
    result = agent.run_full_deduction()
    # result phải có (dict hoặc dataclass):
    #   result.sat_calls        (int)
    #   result.decisions        (int)
    #   result.propagations     (int)
    #   result.backtracks       (int)
    #   result.deduction_steps  (int)
    #   result.runtime_seconds  (float)
    #   result.solved           (bool)
    #   result.trace            (list)  # step-by-step deduction trace
"""

import argparse
import csv
import json
import time
from pathlib import Path

# --- Thử import pipeline thật; nếu chưa có thì chạy dry-run ---
try:
    from logic.cnf_encoder import CNFEncoder
    from logic.logic_agent import LogicAgent
    PIPELINE_READY = True
except ImportError:
    PIPELINE_READY = False


def load_puzzle(path: Path) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def public_puzzle_view(puzzle: dict) -> dict:
    """
    Trả về bản sao puzzle KHÔNG chứa 'solution' — đây là dữ liệu
    hợp lệ để đưa cho Logic Agent (đúng yêu cầu tách bạch Engine/Agent).
    """
    return {
        "id": puzzle["id"],
        "grid_size": puzzle["grid_size"],
        "characters": puzzle["characters"],
        "clues": puzzle["clues"],
        "initial_revealed": puzzle["initial_revealed"],
    }


def run_dry(puzzle: dict) -> dict:
    """Chế độ chạy khi chưa có encoder/agent thật — chỉ đo việc load + validate."""
    start = time.perf_counter()
    n_chars = len(puzzle["characters"])
    n_clues = len(puzzle["clues"])
    elapsed = time.perf_counter() - start
    return {
        "stage_id": puzzle["id"],
        "grid_size": puzzle["grid_size"],
        "num_primary_vars": n_chars,
        "num_aux_vars": "N/A (dry-run)",
        "num_clauses": "N/A (dry-run)",
        "sat_calls": "N/A (dry-run)",
        "decisions": "N/A (dry-run)",
        "propagations": "N/A (dry-run)",
        "backtracks": "N/A (dry-run)",
        "deduction_steps": "N/A (dry-run)",
        "runtime_seconds": round(elapsed, 6),
        "solved": "N/A (dry-run)",
        "note": f"{n_clues} clues loaded OK, pipeline not implemented yet",
    }


def run_real(puzzle: dict) -> dict:
    """Chế độ chạy thật khi logic/cnf_encoder.py và logic/logic_agent.py đã sẵn sàng."""
    view = public_puzzle_view(puzzle)

    start = time.perf_counter()
    agent = LogicAgent(view)
    result = agent.run_full_deduction()
    elapsed = time.perf_counter() - start

    return {
        "stage_id": puzzle["id"],
        "grid_size": puzzle["grid_size"],
        "num_primary_vars": len(puzzle["characters"]),
        "num_aux_vars": getattr(result, "num_aux_vars", "?"),
        "num_clauses": getattr(result, "num_clauses", "?"),
        "sat_calls": getattr(result, "sat_calls", "?"),
        "decisions": getattr(result, "decisions", "?"),
        "propagations": getattr(result, "propagations", "?"),
        "backtracks": getattr(result, "backtracks", "?"),
        "deduction_steps": getattr(result, "deduction_steps", "?"),
        "runtime_seconds": round(elapsed, 6),
        "solved": getattr(result, "solved", "?"),
        "note": "",
    }


def main():
    parser = argparse.ArgumentParser(description="Run Griductive experiments on all stages.")
    parser.add_argument("--stages-dir", default="Source/stages", help="Folder containing puzzle .json files")
    parser.add_argument("--out", default="experiments/results/results.csv", help="Output CSV path")
    args = parser.parse_args()

    stages_dir = Path(args.stages_dir)
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    stage_files = sorted(stages_dir.glob("*.json"))
    if not stage_files:
        print(f"[!] Không tìm thấy puzzle nào trong {stages_dir}")
        return

    mode = "REAL PIPELINE" if PIPELINE_READY else "DRY-RUN (chưa có encoder/agent)"
    print(f"=== Running experiments — mode: {mode} ===")

    rows = []
    for path in stage_files:
        puzzle = load_puzzle(path)
        try:
            row = run_real(puzzle) if PIPELINE_READY else run_dry(puzzle)
        except Exception as e:
            row = {"stage_id": puzzle.get("id", path.stem), "note": f"FAILED: {e}"}
        rows.append(row)
        print(f"  - {row.get('stage_id')}: {row.get('note', 'OK')}")

    fieldnames = [
        "stage_id", "grid_size", "num_primary_vars", "num_aux_vars",
        "num_clauses", "sat_calls", "decisions", "propagations",
        "backtracks", "deduction_steps", "runtime_seconds", "solved", "note",
    ]
    with open(out_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({k: row.get(k, "") for k in fieldnames})

    print(f"\nĐã ghi kết quả vào: {out_path}")


if __name__ == "__main__":
    main()
