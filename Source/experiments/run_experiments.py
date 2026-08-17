"""
experiments/run_experiments.py
-------------------------------
Chạy toàn bộ puzzle trong Source/stages/ qua pipeline
CNF Encoder -> DPLL Solver -> Deductive Logic Agent, thu thập số liệu
theo đúng yêu cầu mục 4.5 của đề bài.
"""

import argparse
import csv
import time
import sys
from pathlib import Path

# Đảm bảo import được các module từ thư mục Source
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.game_engine import GameEngine
from logic.cnf_encoder import CNFEncoder

def run_real(path: Path) -> dict:
    """Chạy thực nghiệm trên một màn chơi và trích xuất số liệu."""
    # Khởi tạo engine từ file JSON
    engine = GameEngine.from_json(path)
    
    # 1. Thu thập dữ liệu CNF ban đầu (Mã hóa toàn bộ clue để đếm tổng số biến/mệnh đề)
    encoder = CNFEncoder(engine.raw_puzzle_data)
    all_ids = list(engine.raw_puzzle_data.get("clues", {}).keys())
    full_cnf, stats = encoder.encode(engine.raw_puzzle_data["clues"], all_ids)
    
    # 2. Bắt đầu quá trình giải tự động
    start_time = time.perf_counter()
    solved_count = engine.auto_solve()
    total_time = time.perf_counter() - start_time
    
    # Lấy thông tin từ agent và solver sau khi giải xong
    agent = engine.agent
    solver = agent.solver
    
    # Kiểm tra xem ván chơi có được giải quyết hoàn toàn không (không còn ô úp)
    unresolved = [pos for pos in engine.characters.keys() if pos not in engine.public_kb]
    solved = len(unresolved) == 0

    return {
        "stage_id": engine.raw_puzzle_data.get("id", path.stem),
        "grid_size": engine.grid_size,
        "num_primary_vars": stats["num_primary_vars"],
        "num_aux_vars": stats["num_aux_vars"],
        "num_clauses": stats["num_clauses"],
        "sat_calls": solver.sat_calls,
        "decisions": solver.decisions,
        "propagations": solver.propagations,
        "backtracks": solver.backtracks,
        "deduction_steps": len(agent.deduction_trace),
        "runtime_seconds": round(total_time, 6),
        "solved": solved,
        "note": f"Đã giải được {solved_count} ô",
    }

def main():
    parser = argparse.ArgumentParser(description="Run Griductive experiments on all stages.")
    parser.add_argument("--stages-dir", default="Source/stages", help="Folder containing puzzle .json files")
    parser.add_argument("--out", default="Source/experiments/results.csv", help="Output CSV path")
    args = parser.parse_args()

    stages_dir = Path(args.stages_dir)
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    stage_files = sorted(stages_dir.glob("*.json"))
    if not stage_files:
        print(f"[!] Không tìm thấy puzzle nào trong {stages_dir}")
        return

    print("=== Running experiments ===")

    rows = []
    for path in stage_files:
        try:
            row = run_real(path)
        except Exception as e:
            row = {"stage_id": path.stem, "note": f"FAILED: {e}"}
        rows.append(row)
        print(f"  - {row.get('stage_id')}: {row.get('note', 'OK')} | Thời gian: {row.get('runtime_seconds', 'N/A')}s")

    # Các cột dữ liệu chuẩn theo yêu cầu đồ án
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