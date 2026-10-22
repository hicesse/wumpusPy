---
marp: true
theme: default
paginate: true
header: "Wumpus World Simulation — Architecture Deep Dive"
footer: "Technical Architecture & OOP Specification"
---

# Wumpus World Simulation
## Complete Code Architecture, Object-Oriented Design & Agent Intelligence

- Autonomous Multi-Agent Wumpus World in Python
- Strict Model-View-Controller & Decoupled Engine Architecture
- Dumb (Loop-Safe) vs. Smart (Knowledge Base + A* Search) Agents
- Deterministic Replayability via Deep Cloning

---

## 1. High-Level Architecture & Separation of Concerns

### Design Philosophy
- **Zero-Spaghetti Decoupling:** Core logic never renders strings; UI never computes physics.
- **Model-View Pattern:** `world.py`, `agent.py`, and `game.py` return plain Python data dicts.
- **Strategy Pattern:** Agents share a uniform abstract interface: `Agent.decide(percepts, world)`.
- **Replayability:** `World.clone()` allows benchmarking different agents on the exact same layout.

### File Separation
- `world.py` — Grid boundary, hazard placement, percept calculations, ray-casting.
- `agent.py` — `Agent` (base), `DumbAgent`, `KnowledgeBase`, `_astar`, `SmartAgent`.
- `game.py` — Turn execution loop, action handler, scoring rules.
- `ui.py` — Unicode box grid rendering, step logs, real-time dual logging to `result.txt`.
- `main.py` — Interactive CLI session, agent factory, replay manager.

---

## 2. Directory & Component Map

| File Name | Role / Layer | Key Classes & Functions | External Dependencies |
| :--- | :--- | :--- | :--- |
| `world.py` | Core Environment / Model | `World`, `turn_left()`, `turn_right()` | `random`, `copy` |
| `agent.py` | Core AI Strategy & KB | `Agent`, `DumbAgent`, `KnowledgeBase`, `SmartAgent`, `_astar` | `world.py`, `heapq`, `random` |
| `game.py` | Core Engine / Controller | `Game`, Scoring Constants | `world.py`, `agent.py`, `ui.py` |
| `ui.py` | Presentation / View | `render_grid()`, `render_step_log()`, `_print()` | `sys`, `io`, `os`, `world.py` |
| `main.py` | Application Entry Point | `main()`, `create_agent()` | `world`, `agent`, `game`, `ui` |
| `tests.py` | Verification & Test Suite | `SuppressOutput`, 8 Automated Test Suites | Standard Python |

---

## 3. Turn Resolution Loop (Percept -> Act Cycle)

```mermaid
flowchart TD
    G1["1. World.get_percepts()"] -->|stench, breeze, glitter, bump, scream| G2["2. Agent.decide()"]
    G2 -->|(action, thought)| G3["3. Game._apply_action()"]
    G3 -->|-1 cost, move/turn/shoot| G4["4. UI Rendering (ui.py)"]
    G4 -->|draw grid, write result.txt| G5["5. Game._check_end_conditions()"]
    G5 -->|continue or game over| G1
```

- Engine queries sensory state from `World`
- Agent evaluates perceptions and returns `(action, thought)`
- Engine verifies kinematics, deducts action cost, and applies state mutations
- Presentation layer logs telemetry to terminal and `result.txt`
- Termination rules evaluated: Win (Gold / Wumpus killed), Lose (Pit / Eaten), or Timeout

---

## 4. `world.py` — Environment Mechanics & Physics

- **Deterministic Seeding:** `World(rows=4, cols=4, seed=None)` uses an isolated `random.Random(seed)` instance.
- **Fixed Origin:** Agent always starts at `(0, 0)` facing `EAST`. Cell `(0, 0)` is guaranteed hazard-free.
- **Hazard Placement:**
  - 1 Wumpus placed outside `(0, 0)`.
  - Scaled Pits: `max(1, (rows * cols * 3) // 16)` placed outside `(0, 0)`.
  - 1 Gold placed on remaining free tile.
- **Sensory Percept Calculation:**
  - `stench`: Living Wumpus on orthogonal neighbor.
  - `breeze`: Pit on orthogonal neighbor.
  - `glitter`: Gold on current cell.
  - `bump` / `scream`: Transient turn flags.
- **Arrow Ray-Casting:** `resolve_arrow(from_pos, dir)` shoots a 1D ray across the board until wall impact or killing the Wumpus.
- **State Cloning:** `World.clone()` uses `copy.deepcopy(self)` for independent replay experiments.

---

## 5. `agent.py` — Base Agent & Loop-Safe DumbAgent

### Abstract Base Class `Agent(ABC)`
- Attributes: `pos (r, c)`, `direction (0-3)`, `has_arrow`, `has_gold`, `is_alive`, `visited`.
- Movement primitives:
  - `do_turn_left()`: Rotates 90° counter-clockwise.
  - `do_turn_right()`: Rotates 90° clockwise.
  - `get_forward_pos()`: Calculates target tile one step ahead.
- Abstract contract: `@abstractmethod decide(percepts, world)`.

### Class `DumbAgent(Agent)` — Loop-Safe Random Explorer
- **Anti-Oscillation:** Maintains `visited` set to eliminate 2-tile infinite ping-pong loops.
- **Decision Priority:**
  1. If `glitter` is perceived $\rightarrow$ immediately return `GRAB`.
  2. If forward tile is unvisited $\rightarrow$ return `MOVE_FORWARD`.
  3. If unvisited neighbor exists $\rightarrow$ rotate toward unvisited tile.
  4. If all adjacent tiles visited $\rightarrow$ randomized escape maneuver.

---

## 6. `agent.py` — KnowledgeBase Inference Engine

### Per-Tile State Matrix
- `UNKNOWN`, `SAFE`, `VISITED`, `POSSIBLE_PIT`, `POSSIBLE_WUMPUS`, `POSSIBLE_DANGER`, `CONFIRMED_PIT`, `CONFIRMED_WUMPUS`.

### Core Deduction Rules (`KnowledgeBase._deduce()`)
- **Zero-Hazard Rule:**
  $$\neg \text{stench} \land \neg \text{breeze} \implies \forall n \in \text{neighbors}, n = \text{SAFE}$$
- **Wumpus Confirmation:**
  If stench perceived and only 1 candidate neighbor remains unconfirmed $\implies$ `CONFIRMED_WUMPUS`.
- **Pit Confirmation:**
  If breeze perceived and unexplained by existing confirmed pits $\implies$ single remaining candidate marked `CONFIRMED_PIT`.
- **Scream Echo:**
  Hearing a scream sets `wumpus_alive = False` and clears all Wumpus suspicion flags across the grid.

---

## 7. `agent.py` — SmartAgent & A* Path Planning

### A* Pathfinder (`_astar`)
- Finds shortest path through verified safe tiles using a priority queue (`heapq`).
- Manhattan heuristic: $h(n) = |r_1 - r_2| + |c_1 - c_2|$.
- Custom `walkable_fn`: Restricts navigation strictly to `KnowledgeBase.is_safe(pos)`.

### SmartAgent Decision Pipeline (`decide()`)
1. Ingest new percepts & trigger `kb.mark_visited()`.
2. Grab gold immediately if `glitter` detected.
3. Pop and execute next action from active plan.
4. If Wumpus location confirmed and arrow available $\rightarrow$ turn & `SHOOT`.
5. Run A* to nearest safe unvisited frontier tile.
6. Fallback: If blocked, calculate risk scores (Pit: 60, Wumpus: 50, Danger: 80) and probe lowest-risk unknown tile.

---

## 8. `game.py` — Rules, Action Handler & Scoring

### Action Penalties & Scoring Constants
- Every Action (`MOVE`, `TURN`, `GRAB`, `SHOOT`): **-1 point**.
- Wasting Arrow (miss): **-10 points**.
- Grabbing Gold: **+1000 points** $\rightarrow$ **WIN**.
- Killing Wumpus with Arrow: **+1000 points** $\rightarrow$ **WIN**.
- Falling into Pit: **-1000 points** $\rightarrow$ **LOSE**.
- Stepping onto live Wumpus: **-1000 points** $\rightarrow$ **LOSE**.
- Step Cap: Default 100 steps $\rightarrow$ **TIMEOUT**.

### Action Dispatcher (`Game._apply_action()`)
- Validates grid boundaries before moving (sets `_just_bumped = True` on wall impact).
- Manages inventory transitions (gold pickup, arrow expenditure).

---

## 9. `ui.py` & `main.py` — Presentation & Session Manager

### `ui.py` (Presentation Layer)
- **Unicode Table Drawing:** Generates `┌─┬─┐` borders, directional arrows (`► ▲ ◄ ▼`), hazard labels (`W, P, G`).
- **Fog of War:** Unvisited tiles remain hidden as `?` until game termination (`reveal_all=True`).
- **Dual Real-Time Logging:** Custom `_print()` mirrors all telemetry simultaneously to `stdout` and `result.txt`.

### `main.py` (Session Controller)
- **Interactive CLI:** Prompts for board size (e.g. 4x4) and agent selection (Dumb vs Smart).
- **Session Loop:**
  - Option 1: Replay **THIS SAME** world (`world.clone()`).
  - Option 2: Generate a **NEW** random world.
  - Option 3: Exit.
- **Teardown Guarantee:** `try...finally` ensures `result.txt` is flushed on exit.

---

## 10. Verification & Benchmark Results

### Automated Test Suite (`tests.py`)
All 8 verification test suites pass with 100% reliability:

| Test Case | Target System | Validated Behavior | Result |
| :--- | :--- | :--- | :--- |
| `test_world_percepts` | `world.py` | Corner/edge percept correctness on seed 42 | **PASS** |
| `test_dumb_agent_loop_prevention` | `agent.py` | Dumb agent visits multiple tiles without looping | **PASS** |
| `test_smart_agent_kb_deduction` | `agent.py` | Zero-hazard & breeze logic propagation | **PASS** |
| `test_smart_agent_astar` | `agent.py` | Optimal pathfinding & obstacle avoidance | **PASS** |
| `test_replay_consistency` | `world.py` | Cloned worlds maintain isolated state | **PASS** |
| `test_full_game_dumb` | `game.py` | 20 batch runs complete without crashing | **PASS** |
| `test_full_game_smart_vs_dumb` | `game.py` | SmartAgent demonstrates superior win rate | **PASS** |
| `test_arrow_mechanic` | `world.py` | Ray-cast arrow resolution and kill state | **PASS** |

---

## 11. PPT Conversion Instructions for Downstream Agents

This workspace provides two ready-to-use bridge formats for converting into `.pptx`:

1. **Structured JSON:** `presentation_deck.json`
   - Complete schema containing slide numbers, titles, layout types, bullet points, tables, and speaker notes.
   - Any agent or script can ingest this JSON and generate slides with `python-pptx` in seconds.

2. **Marp Markdown:** `presentation_slides.md`
   - Can be directly converted with Marp CLI:
     ```bash
     npx @marp-team/marp-cli presentation_slides.md --pptx
     ```

3. **Standalone PDF:** `wumpus_architecture_summary.pdf`
   - Full publication-ready reference manual already compiled in the workspace.
