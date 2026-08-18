# Griductive Solver

A no-guess solver for the **Griductive** grid-deduction game, built for
CSC14003 – Introduction to Artificial Intelligence, Project 2.

The system reimplements the Griductive game with a graphical interface,
automatically encodes revealed clues into CNF, solves them with a
from-scratch DPLL SAT solver, and uses a Deductive Logic Agent to classify
each unresolved character as CRIMINAL, INNOCENT, or UNKNOWN — never
guessing.

## Project Structure

```
Source/
├── main.py                  # GUI entry point (Ursina)
├── core/
│   ├── __init__.py
│   └── game_engine.py       # Game Engine (holds hidden solution + clues)
├── logic/
│   ├── __init__.py
│   ├── cnf_encoder.py       # Clue -> CNF encoder, semantic evaluators
│   ├── dpll.py               # DPLL SAT solver
│   └── agent.py              # Deductive Logic Agent
├── stages/                   # Puzzle files (.json), see docs/puzzle_format.md
├── experiments/
│   ├── run_experiments.py   # Benchmark script
│   └── results.csv           # Latest benchmark output
├── docs/
│   └── puzzle_format.md     # Puzzle JSON format specification
├── requirements.txt
└── README.md
```

## Architecture

Following the assignment's separation requirement, the codebase keeps two
roles strictly apart:

- **Game Engine** (`core/game_engine.py`) owns the complete puzzle,
  including the hidden solution and unrevealed clues.
- **Logic Agent** (`logic/agent.py`) only ever receives the public
  knowledge state (revealed clues and proved verdicts), built internally
  via `GameEngine._public_puzzle()`, which strips the solution before
  passing anything to the CNF Encoder or the Agent.

## Installation

Requires Python 3.10+.

```bash
pip install -r requirements.txt
```

## Running the Game

```bash
cd Source
python main.py
```

Controls:
- **CRIMINAL / INNOCENT** — submit a verdict for the currently selected
  (face-down) card.
- **Hint** — highlights one character whose status is currently provable,
  without revealing it automatically.
- **Auto Solve** — repeatedly finds and reveals every provable character
  until the puzzle is fully solved.
- **Load Next Map** — cycles to the next puzzle file in `stages/`.
- **Restart** — resets the current puzzle back to its initial state.

Click any revealed (face-up) card to see its clue and highlight the cells
it references.

## Running the Benchmark

Runs the full pipeline (CNF Encoder -> DPLL Solver -> Logic Agent) on every
puzzle in `stages/` and writes the results to a CSV file.

```bash
cd Source
python experiments/run_experiments.py --stages-dir stages --out experiments/results.csv
```

For each puzzle, the script records: number of primary/auxiliary variables,
number of CNF clauses, number of SAT calls, decisions, propagations,
backtracks, deduction steps, runtime, whether the puzzle was fully solved,
and the result of the solution-uniqueness check.

## Puzzle Format

Puzzles are plain JSON files in `stages/`. See `docs/puzzle_format.md` for
the full specification (clue types, region kinds, and file structure).

## Team

CSC14003 – Introduction to Artificial Intelligence, Project 2 (Griductive
Solver). See `Report.pdf` for the full project planning and task
distribution.
