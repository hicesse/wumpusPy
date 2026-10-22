"""
ui.py — Presentation layer for Wumpus World

All terminal rendering (ASCII grid, step logs, banners, menus) lives here.
Core game files (world.py, agent.py, game.py) never import this module —
they just hand plain Python dicts to these functions.

Output goes to BOTH the terminal AND result.txt (overwritten each session).

Beginners studying the algorithms can safely ignore this entire file.
"""

import sys
import io
import os

# Ensure stdout can handle Unicode on Windows
if sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    try:
        sys.stdout = io.TextIOWrapper(
            sys.stdout.buffer, encoding="utf-8", errors="replace"
        )
    except Exception:
        pass  # fallback: some chars may not display

from world import DIRECTION_NAMES


# ---------------------------------------------------------------------------
# Dual output — prints to terminal AND writes to result.txt
# ---------------------------------------------------------------------------

# Path to result file (same directory as this script)
_RESULT_DIR = os.path.dirname(os.path.abspath(__file__))
_RESULT_PATH = os.path.join(_RESULT_DIR, "result.txt")

# File handle — opened by open_result_file(), closed by close_result_file()
_result_file = None


def open_result_file():
    """Open result.txt for writing (overwrites previous content)."""
    global _result_file
    _result_file = open(_RESULT_PATH, "w", encoding="utf-8")


def close_result_file():
    """Flush and close result.txt."""
    global _result_file
    if _result_file is not None:
        _result_file.close()
        _result_file = None


def _print(*args, **kwargs):
    """
    Print to both terminal and result.txt.

    Drop-in replacement for the built-in print().
    If result.txt is not open, prints to terminal only.
    """
    # Print to terminal as normal
    print(*args, **kwargs)

    # Also write to result file (if open)
    if _result_file is not None:
        # Capture what print() would produce
        kwargs_copy = dict(kwargs)
        kwargs_copy["file"] = _result_file
        print(*args, **kwargs_copy)

# ---------------------------------------------------------------------------
# Direction symbols for the agent on the grid
# ---------------------------------------------------------------------------
AGENT_ARROWS = {
    "EAST":  "►",
    "NORTH": "▲",
    "WEST":  "◄",
    "SOUTH": "▼",
}


# ---------------------------------------------------------------------------
# Grid renderer
# ---------------------------------------------------------------------------

def render_grid(rows, cols, agent_pos, agent_dir,
                visited, wumpus_pos, pit_positions, gold_pos,
                is_wumpus_alive, reveal_all=False):
    """
    Render the grid as an ASCII/Unicode table.

    Parameters
    ----------
    rows, cols : int
        Grid dimensions.
    agent_pos : tuple(int, int)
        Current agent position.
    agent_dir : int
        Current agent direction (uses DIRECTION_NAMES to map).
    visited : set of tuple(int, int)
        Tiles the agent has stepped on.
    wumpus_pos : tuple(int, int)
    pit_positions : set of tuple(int, int)
    gold_pos : tuple(int, int)
    is_wumpus_alive : bool
    reveal_all : bool
        If True, show all tiles (used for final state / game over).
        If False, only show visited tiles and mark the rest as "?".
    """

    dir_name = DIRECTION_NAMES.get(agent_dir, "EAST")
    agent_symbol = AGENT_ARROWS.get(dir_name, "A")

    # Column width for each cell (characters inside the box)
    cell_w = 6

    # ---- Build top border ----
    top    = "┌" + ("─" * cell_w + "┬") * (cols - 1) + "─" * cell_w + "┐"
    mid    = "├" + ("─" * cell_w + "┼") * (cols - 1) + "─" * cell_w + "┤"
    bottom = "└" + ("─" * cell_w + "┴") * (cols - 1) + "─" * cell_w + "┘"

    lines = [top]

    for r in range(rows):
        row_cells = []
        for c in range(cols):
            pos = (r, c)
            cell_parts = []

            # Decide what to show
            show = reveal_all or pos in visited or pos == agent_pos

            if pos == agent_pos:
                cell_parts.append(agent_symbol)

            if show:
                if pos == wumpus_pos and is_wumpus_alive:
                    cell_parts.append("W")
                elif pos == wumpus_pos and not is_wumpus_alive:
                    cell_parts.append("x")  # dead wumpus
                if pos in pit_positions:
                    cell_parts.append("P")
                if pos == gold_pos:
                    cell_parts.append("G")
            else:
                cell_parts.append("?")

            # Build cell string (center-aligned)
            cell_str = " ".join(cell_parts)
            if len(cell_str) > cell_w:
                cell_str = cell_str[:cell_w]
            cell_str = cell_str.center(cell_w)
            row_cells.append(cell_str)

        row_line = "│" + "│".join(row_cells) + "│"
        lines.append(row_line)

        if r < rows - 1:
            lines.append(mid)

    lines.append(bottom)

    _print("\n".join(lines))

    # Legend
    _print("  Legend: {}=Agent  W=Wumpus  P=Pit  G=Gold  x=Dead Wumpus  ?=Unknown"
          .format(agent_symbol))


# ---------------------------------------------------------------------------
# Step log renderer
# ---------------------------------------------------------------------------

def render_step_log(step_num, agent_pos, agent_dir, percepts, thought,
                    action, score):
    """
    Print a structured step log with labeled tags.

    Parameters
    ----------
    step_num : int
    agent_pos : tuple(int, int)
    agent_dir : int
    percepts : dict
    thought : str
    action : str
    score : int
    """

    dir_name = DIRECTION_NAMES.get(agent_dir, "?")

    _print()
    _print("=" * 60)
    _print("  STEP {}  —  Agent at {} facing {}".format(
        step_num, agent_pos, dir_name
    ))
    _print("=" * 60)

    # Percepts
    active_percepts = [k for k, v in percepts.items() if v]
    if active_percepts:
        percept_str = ", ".join(active_percepts)
    else:
        percept_str = "nothing"
    _print("  [PERCEPT]  I sense: {}".format(percept_str))

    # Thought
    _print("  [THINK]    {}".format(thought))

    # Action
    _print("  [ACTION]   {}".format(action))

    # Score
    _print("  [SCORE]    {}".format(score))
    _print()


# ---------------------------------------------------------------------------
# Banner and game-over displays
# ---------------------------------------------------------------------------

def render_banner(title="WUMPUS WORLD ADVENTURE"):
    """Print a decorative session banner."""
    width = 60
    border = "═" * width
    _print()
    _print("╔" + border + "╗")
    _print("║" + title.center(width) + "║")
    _print("╚" + border + "╝")
    _print()


def render_game_over(status, score, steps, agent_pos, agent_dir,
                     rows, cols, visited, wumpus_pos, pit_positions,
                     gold_pos, is_wumpus_alive):
    """
    Print the final game state with full grid reveal.

    Parameters
    ----------
    status : str
        "WIN" or "LOSE" or "TIMEOUT"
    score : int
    steps : int
    (remaining params passed to render_grid with reveal_all=True)
    """

    _print()
    _print("=" * 60)

    if status == "WIN":
        _print("  🏆  VICTORY!  The agent found the gold!")
    elif status == "LOSE":
        _print("  💀  GAME OVER!  The agent has died!")
    else:
        _print("  ⏱️   TIMEOUT!  Maximum steps reached.")

    _print("=" * 60)
    _print("  Final Score : {}".format(score))
    _print("  Steps Taken : {}".format(steps))
    _print("  Result      : {}".format(status))
    _print("=" * 60)
    _print()
    _print("  --- Final World State (all tiles revealed) ---")
    _print()

    render_grid(
        rows=rows, cols=cols,
        agent_pos=agent_pos, agent_dir=agent_dir,
        visited=visited,
        wumpus_pos=wumpus_pos,
        pit_positions=pit_positions,
        gold_pos=gold_pos,
        is_wumpus_alive=is_wumpus_alive,
        reveal_all=True,
    )

    _print()
# ---------------------------------------------------------------------------
# Menu helpers
# ---------------------------------------------------------------------------

def prompt_grid_size():
    """Ask the user for grid dimensions. Returns (rows, cols)."""
    print("Configure grid size (default 4x4):")
    raw = input("  Enter rows cols (e.g. '4 4'): ").strip()
    if not raw:
        rows, cols = 4, 4
    else:
        parts = raw.split()
        try:
            rows = int(parts[0])
            cols = int(parts[1]) if len(parts) > 1 else rows
            if rows < 2 or cols < 2:
                print("  Grid too small — using 4x4.")
                rows, cols = 4, 4
        except (ValueError, IndexError):
            print("  Invalid input — using 4x4.")
            rows, cols = 4, 4

    # Log the choice to result file
    _print("  Grid size: {}x{}".format(rows, cols))
    return rows, cols


def prompt_agent_mode():
    """Ask the user to pick Dumb or Smart agent. Returns 1 or 2."""
    print("Select agent mode:")
    print("  [1] Dumb Agent  (loop-safe random walk)")
    print("  [2] Smart Agent (Knowledge Base + A* Search)")
    raw = input("  Enter 1 or 2: ").strip()
    mode = 2 if raw == "2" else 1
    mode_name = "Smart Agent (A*)" if mode == 2 else "Dumb Agent"
    _print("  Agent mode: {}".format(mode_name))
    return mode


def prompt_post_game():
    """
    Post-game menu. Returns 1, 2, or 3.
      1 = replay same world
      2 = new world
      3 = exit
    """
    print("What would you like to do?")
    print("  [1] Replay THIS SAME world (try another agent mode)")
    print("  [2] Start a NEW random world")
    print("  [3] Exit")
    raw = input("  Enter 1, 2, or 3: ").strip()
    if raw in ("1", "2", "3"):
        return int(raw)
    return 3
