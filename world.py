"""
world.py — World Representation for Wumpus World

Handles: grid dimensions, hazard placement (Wumpus, Pits, Gold),
         percept calculation (stench, breeze, glitter, bump, scream),
         arrow resolution, and world cloning for replay sessions.
"""

import copy
import random


# ---------------------------------------------------------------------------
# Direction constants
# ---------------------------------------------------------------------------
# Each direction maps to a (delta_row, delta_col) movement vector.
#   Row increases downward,  Col increases rightward.
#
#       NORTH = row - 1
#       SOUTH = row + 1
#       EAST  = col + 1
#       WEST  = col - 1

EAST  = 0
NORTH = 1
WEST  = 2
SOUTH = 3

DIRECTION_NAMES = {
    EAST:  "EAST",
    NORTH: "NORTH",
    WEST:  "WEST",
    SOUTH: "SOUTH",
}

DIRECTION_DELTAS = {
    EAST:  (0,  1),   # same row, next column
    NORTH: (-1, 0),   # previous row, same column
    WEST:  (0, -1),   # same row, previous column
    SOUTH: (1,  0),   # next row, same column
}

# Turn helpers  (directions are numbered 0-3 clockwise from EAST)
def turn_left(direction):
    """Rotate 90° counter-clockwise: EAST -> NORTH -> WEST -> SOUTH -> EAST."""
    return (direction + 1) % 4

def turn_right(direction):
    """Rotate 90° clockwise: EAST -> SOUTH -> WEST -> NORTH -> EAST."""
    return (direction - 1) % 4


# ---------------------------------------------------------------------------
# World class
# ---------------------------------------------------------------------------

class World:
    """
    A grid-based Wumpus World.

    Attributes
    ----------
    rows, cols : int
        Grid dimensions.
    wumpus_pos : tuple(int, int)
        Location of the Wumpus.
    pit_positions : set of tuple(int, int)
        Locations of all pits.
    gold_pos : tuple(int, int)
        Location of the gold.
    is_wumpus_alive : bool
        Whether the Wumpus is still alive.
    """

    def __init__(self, rows=4, cols=4, seed=None):
        """
        Build a random world.

        Parameters
        ----------
        rows, cols : int
            Grid size (default 4×4).
        seed : int or None
            If provided, the random placement is deterministic so the
            exact same world can be reproduced for replay / testing.
        """
        self.rows = rows
        self.cols = cols

        # Use a local Random instance so we don't disturb the global state.
        rng = random.Random(seed)

        # Every coordinate on the grid
        all_positions = [
            (r, c) for r in range(rows) for c in range(cols)
        ]

        # Agent always starts at (0, 0) — that cell must be hazard-free.
        agent_start = (0, 0)
        available = [pos for pos in all_positions if pos != agent_start]

        # --- Place Wumpus (exactly 1) ---
        self.wumpus_pos = rng.choice(available)
        available.remove(self.wumpus_pos)

        # --- Place Pits ---
        # Scale pit count with grid area: roughly 3 pits per 16 tiles.
        pit_count = max(1, (rows * cols * 3) // 16)
        pit_count = min(pit_count, len(available))  # safety cap
        self.pit_positions = set(rng.sample(available, pit_count))
        available = [pos for pos in available if pos not in self.pit_positions]

        # --- Place Gold (exactly 1) ---
        self.gold_pos = rng.choice(available)

        # Wumpus starts alive
        self.is_wumpus_alive = True

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------

    def is_valid(self, pos):
        """Return True if *pos* is inside the grid boundaries."""
        r, c = pos
        return 0 <= r < self.rows and 0 <= c < self.cols

    def adjacent(self, pos):
        """Return a list of valid neighbor positions (up/down/left/right)."""
        r, c = pos
        neighbors = []
        for dr, dc in DIRECTION_DELTAS.values():
            nr, nc = r + dr, c + dc
            if self.is_valid((nr, nc)):
                neighbors.append((nr, nc))
        return neighbors

    def get_percepts(self, pos, just_bumped=False, scream_heard=False):
        """
        Compute what the agent perceives at *pos*.

        Parameters
        ----------
        pos : tuple(int, int)
            The agent's current position.
        just_bumped : bool
            True if the agent just tried to move into a wall.
        scream_heard : bool
            True if the Wumpus was just killed this turn.

        Returns
        -------
        dict with keys: stench, breeze, glitter, bump, scream
            Each value is a bool.
        """
        neighbors = self.adjacent(pos)

        # Stench: an adjacent tile contains a *living* Wumpus
        stench = (
            self.is_wumpus_alive
            and self.wumpus_pos in neighbors
        )

        # Breeze: an adjacent tile contains a pit
        breeze = any(n in self.pit_positions for n in neighbors)

        # Glitter: gold is on the agent's current tile
        glitter = (pos == self.gold_pos)

        return {
            "stench":  stench,
            "breeze":  breeze,
            "glitter": glitter,
            "bump":    just_bumped,
            "scream":  scream_heard,
        }

    def resolve_arrow(self, from_pos, direction):
        """
        Fire an arrow from *from_pos* in the given *direction*.

        The arrow travels in a straight line until it hits a wall or
        the Wumpus. If it hits the Wumpus, the Wumpus dies.

        Returns
        -------
        bool
            True if the Wumpus was hit and killed.
        """
        if not self.is_wumpus_alive:
            return False

        dr, dc = DIRECTION_DELTAS[direction]
        r, c = from_pos

        while True:
            r, c = r + dr, c + dc
            if not self.is_valid((r, c)):
                return False          # arrow flew off the grid — miss
            if (r, c) == self.wumpus_pos:
                self.is_wumpus_alive = False
                return True           # hit!

    # ------------------------------------------------------------------
    # Cloning (for replay sessions)
    # ------------------------------------------------------------------

    def clone(self):
        """Return an independent deep copy of this World."""
        return copy.deepcopy(self)
