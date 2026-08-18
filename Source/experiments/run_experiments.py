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

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.game_engine import GameEngine
from logic.cnf_encoder import CNFEncoder


def run_real(path: Path) -> dict:
    """Chạy thực nghiệm trên một màn chơi và trích xuất số liệu."""
    engine = GameEngine.from_json(path)

    # 1. Thu thập dữ liệu CNF ban đầu — dùng _public_puzzle() (KHÔNG có 'solution'),
    #    không bao giờ truyền engine.raw_puzzle_data thẳng cho CNFEncoder.
    encoder = CNFEncoder(engine._public_puzzle())
    public_clues = engine._public_puzzle()["clues"]
    all_ids = list(public_clues.keys())
    full_cnf, stats = encoder.encode(public_clues, all_ids)

    # 2. Chạy Auto Solve thật
    start_time = time.perf_counter()
    solved_count = engine.auto_solve()
    total_time = time.perf_counter() - start_time

    agent = engine.agent
    solver = agent.solver

    unresolved = [pos for pos in engine.characters.keys() if pos not in engine.public_kb]
    solved = len(unresolved) == 0

    # 3. Uniqueness check (mục 4.4) — ghi kèm vào kết quả benchmark để report
    #    có bằng chứng thực nghiệm cho tính năng này, không chỉ mô tả suông.
    uniqueness = engine.check_uniqueness()

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
        "uniqueness_status": uniqueness["status"],
        "uniqueness_sat_calls": uniqueness["num_sat_calls"],
        "note": f"Da giai duoc {solved_count} o",
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
        print(f"[!] Khong tim thay puzzle nao trong {stages_dir}")
        return

    print("=== Running experiments ===")

    rows = []
    for path in stage_files:
        try:
            row = run_real(path)
        except Exception as e:
            row = {"stage_id": path.stem, "note": f"FAILED: {e}"}
        rows.append(row)
        print(f"  - {row.get('stage_id')}: {row.get('note', 'OK')} | Thoi gian: {row.get('runtime_seconds', 'N/A')}s")

    fieldnames = [
        "stage_id", "grid_size", "num_primary_vars", "num_aux_vars",
        "num_clauses", "sat_calls", "decisions", "propagations",
        "backtracks", "deduction_steps", "runtime_seconds", "solved",
        "uniqueness_status", "uniqueness_sat_calls", "note",
    ]

    # utf-8-sig (có BOM) để Excel mở đúng tiếng Việt thay vì hiện ký tự lỗi font
    with open(out_path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({k: row.get(k, "") for k in fieldnames})

    print(f"\nDa ghi ket qua vao: {out_path}")


if __name__ == "__main__":
    main()
