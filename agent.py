"""
agent.py — Agent classes for Wumpus World

Contains:
    Agent      — abstract base class with shared movement logic.
    DumbAgent  — random-walk agent that avoids revisiting tiles.
    SmartAgent — knowledge-based agent with A* pathfinding.
"""

import random
from abc import ABC, abstractmethod

from world import (
    EAST, NORTH, WEST, SOUTH,
    DIRECTION_NAMES, DIRECTION_DELTAS,
    turn_left, turn_right,
)


# ---------------------------------------------------------------------------
# Action constants  (plain strings — easy for beginners to read)
# ---------------------------------------------------------------------------
MOVE_FORWARD = "MOVE_FORWARD"
TURN_LEFT    = "TURN_LEFT"
TURN_RIGHT   = "TURN_RIGHT"
GRAB         = "GRAB"
SHOOT        = "SHOOT"


# ---------------------------------------------------------------------------
# Base Agent
# ---------------------------------------------------------------------------

class Agent(ABC):
    """
    Abstract base class for every Wumpus World agent.

    Attributes
    ----------
    pos : tuple(int, int)
        Current grid position (row, col).
    direction : int
        Current facing direction (EAST / NORTH / WEST / SOUTH).
    has_arrow : bool
        Whether the agent still has an arrow to shoot.
    has_gold : bool
        Whether the agent is carrying the gold.
    is_alive : bool
        Whether the agent is still alive.
    visited : set of tuple(int, int)
        Tiles the agent has already stood on.
    """

    def __init__(self):
        self.pos       = (0, 0)
        self.direction = EAST
        self.has_arrow = True
        self.has_gold  = False
        self.is_alive  = True
        self.visited   = {(0, 0)}       # start tile counts as visited

    # ---- movement helpers ----

    def do_turn_left(self):
        """Rotate 90° counter-clockwise."""
        self.direction = turn_left(self.direction)

    def do_turn_right(self):
        """Rotate 90° clockwise."""
        self.direction = turn_right(self.direction)

    def get_forward_pos(self):
        """Return the tile one step ahead in the current facing direction."""
        dr, dc = DIRECTION_DELTAS[self.direction]
        r, c = self.pos
        return (r + dr, c + dc)

    # ---- abstract interface ----

    @abstractmethod
    def decide(self, percepts, world):
        """
        Choose the next action based on current percepts.

        Must return a tuple ``(action, thought)`` where *action* is one of
        the action constants and *thought* is a human-readable explanation.

        Parameters
        ----------
        percepts : dict
            The percept dictionary from ``World.get_percepts()``.
        world : World
            Reference to the world (SmartAgent uses grid size;
            DumbAgent only needs ``is_valid``).
        """
        ...


# ---------------------------------------------------------------------------
# Dumb Agent — loop-safe random walk
# ---------------------------------------------------------------------------

class DumbAgent(Agent):
    """
    An agent that knows *nothing* about hazards.

    It wanders randomly but tracks which tiles it has visited so it
    prefers unvisited neighbors — this prevents aimless ping-ponging.
    If it senses glitter, it grabs the gold immediately.
    """

    def decide(self, percepts, world):
        """Pick a random-ish action; prefer unexplored tiles."""

        # ---- Rule 1: grab gold if we see glitter ----
        if percepts["glitter"]:
            return (GRAB, "I see something shiny! Grabbing the gold!")

        # ---- Collect info about neighbors ----
        forward_pos = self.get_forward_pos()
        forward_valid = world.is_valid(forward_pos)
        forward_visited = forward_pos in self.visited

        # Build a list of *all* reachable adjacent tiles and whether
        # they've been visited, so we can reason about turning.
        unvisited_directions = []
        visited_directions   = []

        for d in [EAST, NORTH, WEST, SOUTH]:
            dr, dc = DIRECTION_DELTAS[d]
            nr, nc = self.pos[0] + dr, self.pos[1] + dc
            neighbor = (nr, nc)
            if world.is_valid(neighbor):
                if neighbor not in self.visited:
                    unvisited_directions.append(d)
                else:
                    visited_directions.append(d)

        # ---- Rule 2: prefer moving toward unvisited tiles ----

        # If forward is valid AND unvisited, go straight
        if forward_valid and not forward_visited:
            thought = (
                "Tile {} ahead is unexplored — moving forward."
                .format(forward_pos)
            )
            return (MOVE_FORWARD, thought)

        # If there are unvisited tiles in other directions, turn toward one
        if unvisited_directions:
            # Pick one unvisited direction at random
            target_dir = random.choice(unvisited_directions)
            target_tile_dr, target_tile_dc = DIRECTION_DELTAS[target_dir]
            target_tile = (
                self.pos[0] + target_tile_dr,
                self.pos[1] + target_tile_dc,
            )

            # Decide which turn gets us facing that direction
            if target_dir == self.direction:
                # Already facing it (but the tile is visited — shouldn't
                # reach here, but just in case)
                thought = (
                    "Facing {} toward tile {} — moving forward."
                    .format(DIRECTION_NAMES[self.direction], target_tile)
                )
                return (MOVE_FORWARD, thought)

            # Turn left or right?  Pick the shortest rotation.
            left_once = turn_left(self.direction)
            if left_once == target_dir:
                thought = (
                    "Turning left to face {} — tile {} is unexplored."
                    .format(DIRECTION_NAMES[target_dir], target_tile)
                )
                return (TURN_LEFT, thought)
            else:
                thought = (
                    "Turning right to face {} — tile {} is unexplored."
                    .format(DIRECTION_NAMES[target_dir], target_tile)
                )
                return (TURN_RIGHT, thought)

        # ---- Rule 3: all adjacent tiles visited — random escape ----
        # Pick a random action to avoid getting stuck.
        action = random.choice([MOVE_FORWARD, TURN_LEFT, TURN_RIGHT])
        if action == MOVE_FORWARD and forward_valid:
            thought = (
                "All neighbors visited. Moving forward to {} anyway."
                .format(forward_pos)
            )
        elif action == MOVE_FORWARD and not forward_valid:
            # Would bump, turn instead
            action = random.choice([TURN_LEFT, TURN_RIGHT])
            thought = "All neighbors visited. Turning randomly to find a way."
        else:
            thought = "All neighbors visited. Turning randomly to find a way."

        return (action, thought)



# ---------------------------------------------------------------------------
# Knowledge Base — used by SmartAgent to track what it knows
# ---------------------------------------------------------------------------

# Tile status constants
UNKNOWN          = "UNKNOWN"
SAFE             = "SAFE"
VISITED          = "VISITED"          # visited implies safe
POSSIBLE_PIT     = "POSSIBLE_PIT"
POSSIBLE_WUMPUS  = "POSSIBLE_WUMPUS"
POSSIBLE_DANGER  = "POSSIBLE_DANGER"  # could be pit or wumpus
CONFIRMED_PIT    = "CONFIRMED_PIT"
CONFIRMED_WUMPUS = "CONFIRMED_WUMPUS"


class KnowledgeBase:
    """
    Tracks what the SmartAgent knows about each tile.

    For every tile visited, we record the percepts and deduce the
    safety of neighboring tiles.  The deduction rules are:

    1. If a tile has NO stench and NO breeze → all its neighbors are SAFE.
    2. If a tile has stench → unvisited neighbors *might* have the Wumpus.
    3. If a tile has breeze → unvisited neighbors *might* have a pit.
    4. Cross-referencing multiple observations can confirm exact locations.
    """

    def __init__(self, rows, cols):
        self.rows = rows
        self.cols = cols

        # status[r][c] = one of the status constants above
        self.status = [
            [UNKNOWN for _ in range(cols)]
            for _ in range(rows)
        ]

        # percepts_at[(r,c)] = percept dict recorded when we visited that tile
        self.percepts_at = {}

        # The start tile is safe and visited
        self.status[0][0] = VISITED

        # Track wumpus state
        self.wumpus_alive = True
        self.wumpus_location = None      # set when confirmed

# deltarow deltacolom
    def _neighbors(self, pos):
        """Return valid adjacent positions."""
        r, c = pos
        result = []
        for dr, dc in DIRECTION_DELTAS.values():
            nr, nc = r + dr, c + dc
            if 0 <= nr < self.rows and 0 <= nc < self.cols:
                result.append((nr, nc))
        return result

    def mark_visited(self, pos, percepts):
        """
        Record that we visited *pos* and observed *percepts*.
        Then run deduction to update neighbor statuses.
        """
        r, c = pos
        self.status[r][c] = VISITED
        self.percepts_at[pos] = percepts

        if percepts.get("scream"):
            self.wumpus_alive = False
            # Clear any wumpus suspicions
            for rr in range(self.rows):
                for cc in range(self.cols):
                    if self.status[rr][cc] in (POSSIBLE_WUMPUS, POSSIBLE_DANGER):
                        self.status[rr][cc] = (
                            POSSIBLE_PIT if self.status[rr][cc] == POSSIBLE_DANGER
                            else SAFE
                        )

        self._deduce()

    def _deduce(self):
        """
        Run deduction rules across all visited tiles.

        Called after every new observation to propagate knowledge.
        """
        changed = True
        iterations = 0
        max_iterations = self.rows * self.cols * 10  # safety cap

        while changed and iterations < max_iterations:
            changed = False
            iterations += 1

            for pos, percepts in self.percepts_at.items():
                neighbors = self._neighbors(pos)

                has_stench = percepts["stench"]
                has_breeze = percepts["breeze"]

                # ------ Rule 1: no hazard signals → neighbors are safe ------
                if not has_stench and not has_breeze:
                    for n in neighbors:
                        nr, nc = n
                        if self.status[nr][nc] in (
                            UNKNOWN, POSSIBLE_PIT, POSSIBLE_WUMPUS,
                            POSSIBLE_DANGER
                        ):
                            self.status[nr][nc] = SAFE
                            changed = True

                # ------ Rule 2: stench → unvisited neighbors might be wumpus
                if has_stench and self.wumpus_alive:
                    # Only consider neighbors that could hold the wumpus
                    suspect_neighbors = [
                        n for n in neighbors
                        if self.status[n[0]][n[1]] in (
                            UNKNOWN, POSSIBLE_WUMPUS, POSSIBLE_DANGER,
                            CONFIRMED_WUMPUS
                        )
                    ]
                    # Check if the stench is already explained by a
                    # confirmed wumpus neighbor — if so, skip marking.
                    already_explained = any(
                        self.status[n[0]][n[1]] == CONFIRMED_WUMPUS
                        for n in neighbors
                    )

                    if not already_explained:
                        unconfirmed = [
                            n for n in suspect_neighbors
                            if self.status[n[0]][n[1]] != CONFIRMED_WUMPUS
                        ]
                        # If exactly one candidate → confirmed wumpus
                        if len(unconfirmed) == 1:
                            wr, wc = unconfirmed[0]
                            if self.status[wr][wc] != CONFIRMED_WUMPUS:
                                self.status[wr][wc] = CONFIRMED_WUMPUS
                                self.wumpus_location = (wr, wc)
                                changed = True
                        else:
                            for n in unconfirmed:
                                nr, nc = n
                                if self.status[nr][nc] == UNKNOWN:
                                    self.status[nr][nc] = POSSIBLE_WUMPUS
                                    changed = True
                                elif self.status[nr][nc] == POSSIBLE_PIT:
                                    self.status[nr][nc] = POSSIBLE_DANGER
                                    changed = True

                # ------ Rule 3: breeze → unvisited neighbors might be pit
                if has_breeze:
                    # Check if the breeze is already fully explained by
                    # a confirmed pit neighbor.
                    has_confirmed_pit_neighbor = any(
                        self.status[n[0]][n[1]] == CONFIRMED_PIT
                        for n in neighbors
                    )

                    suspect_neighbors = [
                        n for n in neighbors
                        if self.status[n[0]][n[1]] in (
                            UNKNOWN, POSSIBLE_PIT, POSSIBLE_DANGER
                        )
                    ]

                    if has_confirmed_pit_neighbor:
                        # Breeze is already explained — do NOT confirm
                        # any remaining unknowns as pits.  But still
                        # mark unknowns as *possible* pits.
                        for n in suspect_neighbors:
                            nr, nc = n
                            if self.status[nr][nc] == UNKNOWN:
                                self.status[nr][nc] = POSSIBLE_PIT
                                changed = True
                    else:
                        # No confirmed pit explains this breeze yet.
                        if len(suspect_neighbors) == 1:
                            pr, pc = suspect_neighbors[0]
                            if self.status[pr][pc] != CONFIRMED_PIT:
                                self.status[pr][pc] = CONFIRMED_PIT
                                changed = True
                        else:
                            for n in suspect_neighbors:
                                nr, nc = n
                                if self.status[nr][nc] == UNKNOWN:
                                    self.status[nr][nc] = POSSIBLE_PIT
                                    changed = True
                                elif self.status[nr][nc] == POSSIBLE_WUMPUS:
                                    self.status[nr][nc] = POSSIBLE_DANGER
                                    changed = True

                # ------ Rule 4: if wumpus confirmed, clear other suspicions
                if self.wumpus_location is not None:
                    for rr in range(self.rows):
                        for cc in range(self.cols):
                            if (rr, cc) != self.wumpus_location:
                                if self.status[rr][cc] == POSSIBLE_WUMPUS:
                                    self.status[rr][cc] = SAFE
                                    changed = True
                                elif self.status[rr][cc] == POSSIBLE_DANGER:
                                    self.status[rr][cc] = POSSIBLE_PIT
                                    changed = True

    def get_safe_unvisited(self):
        """Return a set of tiles known to be SAFE but not yet VISITED."""
        result = set()
        for r in range(self.rows):
            for c in range(self.cols):
                if self.status[r][c] == SAFE:
                    result.add((r, c))
        return result

    def get_visited(self):
        """Return a set of all visited tiles."""
        result = set()
        for r in range(self.rows):
            for c in range(self.cols):
                if self.status[r][c] == VISITED:
                    result.add((r, c))
        return result

    def is_safe(self, pos):
        """Return True if a tile is known safe or visited."""
        r, c = pos
        return self.status[r][c] in (SAFE, VISITED)

    def tile_status_str(self, pos):
        """Return human-readable status of a tile."""
        r, c = pos
        return self.status[r][c]


# ---------------------------------------------------------------------------
# A* Pathfinder  (used internally by SmartAgent)
# ---------------------------------------------------------------------------

import heapq

def _astar(start, goal, walkable_fn, neighbors_fn):
    """
    A* search from *start* to *goal*.

    Parameters
    ----------
    start, goal : tuple(int, int)
    walkable_fn : callable(pos) -> bool
        Returns True if the tile can be walked on.
    neighbors_fn : callable(pos) -> list of tuple(int, int)
        Returns valid adjacent tiles.

    Returns
    -------
    list of tuple(int, int)
        Path from start to goal (inclusive of both endpoints),
        or an empty list if no path exists.
    """
    # f(n) = g(n) + h(n)
    # h(n) = Manhattan distance to goal
    def heuristic(a, b):
        return abs(a[0] - b[0]) + abs(a[1] - b[1])

    open_set = []  # min-heap of (f_score, counter, node)
    counter = 0
    heapq.heappush(open_set, (heuristic(start, goal), counter, start))
    counter += 1

    came_from = {}
    g_score = {start: 0}

    while open_set:
        _, _, current = heapq.heappop(open_set)

        if current == goal:
            # Reconstruct path
            path = [current]
            while current in came_from:
                current = came_from[current]
                path.append(current)
            path.reverse()
            return path

        for neighbor in neighbors_fn(current):
            if not walkable_fn(neighbor) and neighbor != goal:
                continue

            tentative_g = g_score[current] + 1

            if tentative_g < g_score.get(neighbor, float("inf")):
                came_from[neighbor] = current
                g_score[neighbor] = tentative_g
                f = tentative_g + heuristic(neighbor, goal)
                heapq.heappush(open_set, (f, counter, neighbor))
                counter += 1

    return []  # no path found


# ---------------------------------------------------------------------------
# Smart Agent — Knowledge Base + A* Search
# ---------------------------------------------------------------------------

class SmartAgent(Agent):
    """
    An agent that reasons about hazards using a KnowledgeBase
    and plans paths with A* search.

    It tracks percepts at every visited tile, deduces which tiles
    are safe or dangerous, and always explains its reasoning.
    """

    def __init__(self, rows=4, cols=4):
        super().__init__()
        self.kb = KnowledgeBase(rows, cols)
        self.rows = rows
        self.cols = cols
        self.plan = []        # queued actions to execute
        self.path = []        # planned tile path (for display)
        self.first_step = True

    def _neighbors(self, pos):
        """Return valid adjacent positions within the grid."""
        r, c = pos
        result = []
        for dr, dc in DIRECTION_DELTAS.values():
            nr, nc = r + dr, c + dc
            if 0 <= nr < self.rows and 0 <= nc < self.cols:
                result.append((nr, nc))
        return result

    def _direction_to(self, from_pos, to_pos):
        """Return which direction to face to step from from_pos to to_pos."""
        dr = to_pos[0] - from_pos[0]
        dc = to_pos[1] - from_pos[1]
        for d, (ddr, ddc) in DIRECTION_DELTAS.items():
            if (ddr, ddc) == (dr, dc):
                return d
        return None

    def _turns_to_face(self, current_dir, target_dir):
        """
        Return a list of TURN_LEFT / TURN_RIGHT actions to rotate
        from current_dir to target_dir (shortest path).
        """
        if current_dir == target_dir:
            return []

        # Try turning left
        steps_left = 0
        d = current_dir
        while d != target_dir and steps_left < 4:
            d = turn_left(d)
            steps_left += 1

        # Try turning right
        steps_right = 0
        d = current_dir
        while d != target_dir and steps_right < 4:
            d = turn_right(d)
            steps_right += 1

        if steps_left <= steps_right:
            return [TURN_LEFT] * steps_left
        else:
            return [TURN_RIGHT] * steps_right

    def _plan_path_actions(self, path):
        """
        Convert a tile-path into a sequence of TURN + MOVE actions.
        The path includes the current tile as the first element.
        """
        actions = []
        current_dir = self.direction

        for i in range(len(path) - 1):
            needed_dir = self._direction_to(path[i], path[i + 1])
            if needed_dir is None:
                continue
            # Turn to face the right direction
            turns = self._turns_to_face(current_dir, needed_dir)
            actions.extend(turns)
            # Move forward
            actions.append(MOVE_FORWARD)
            current_dir = needed_dir

        return actions

    def _plan_to_nearest(self, targets):
        """
        Find the closest target tile (from a set) using A* through
        safe/visited tiles, build a plan, and return (action, thought).
        Returns None if no reachable target found.
        """
        best_path = None
        best_target = None
        best_cost = float("inf")

        for target in targets:
            path = _astar(
                start=self.pos,
                goal=target,
                walkable_fn=lambda p: self.kb.is_safe(p),
                neighbors_fn=self._neighbors,
            )
            if path and len(path) < best_cost:
                best_cost = len(path)
                best_path = path
                best_target = target

        if best_path and len(best_path) > 1:
            self.path = best_path
            self.plan = self._plan_path_actions(best_path)

            # Describe reasoning
            target_status = self.kb.tile_status_str(best_target)
            neighbors_info = []
            for n in self._neighbors(best_target):
                ns = self.kb.tile_status_str(n)
                neighbors_info.append("{}: {}".format(n, ns))

            thought = (
                "Chose tile {} because it is {} and nearest safe "
                "unexplored tile (distance {}). "
                "Neighbors: [{}]"
                .format(
                    best_target,
                    target_status,
                    best_cost - 1,
                    ", ".join(neighbors_info),
                )
            )

            if self.plan:
                action = self.plan.pop(0)
                return (action, thought)

        return None

    def decide(self, percepts, world):
        """
        Make a decision using knowledge base reasoning and A* planning.
        Returns (action, thought_string).
        """

        # ---- Record percepts in knowledge base ----
        new_tile = self.pos not in self.kb.percepts_at
        if self.first_step or new_tile:
            self.kb.mark_visited(self.pos, percepts)
            self.first_step = False
            # Arriving at a new tile invalidates any old plan — we need
            # to re-evaluate based on fresh KB deductions.
            if new_tile:
                self.plan.clear()

        # ---- Rule 1: grab gold if we see glitter ----
        if percepts["glitter"]:
            self.plan.clear()
            return (GRAB, "Glitter detected! Grabbing the gold!")

        # ---- Rule 2: if we have queued actions, execute the next one ----
        if self.plan:
            action = self.plan.pop(0)
            thought = "Executing planned action: {} (path: {})".format(
                action, " -> ".join(str(t) for t in self.path)
            )
            return (action, thought)

        # ---- Rule 3: strategic shooting ----
        # If wumpus location is confirmed (or strongly suspected) and
        # we have an arrow, try to shoot from current position.
        if self.has_arrow and self.kb.wumpus_location is not None:
            shoot_result = self._try_shoot_wumpus(self.kb.wumpus_location)
            if shoot_result is not None:
                return shoot_result

        # ---- Rule 4: plan path to nearest safe unvisited tile ----
        safe_targets = self.kb.get_safe_unvisited()

        if safe_targets:
            result = self._plan_to_nearest(safe_targets)
            if result is not None:
                return result

        # ---- Rule 5: no safe tiles — try shooting suspected wumpus ----
        if self.has_arrow and self.kb.wumpus_alive:
            # Try to navigate to a position where we can shoot a suspect
            shoot_result = self._try_shoot_suspected_wumpus()
            if shoot_result is not None:
                return shoot_result

        # ---- Rule 6: no safe tiles left — pick the least dangerous
        #      *unvisited* neighbor and go there.  Visited tiles are
        #      excluded because re-entering them makes zero progress.
        #      If no direct unvisited neighbor exists, A* through visited
        #      tiles to reach the nearest unvisited tile on the grid.

        # First try: direct unvisited neighbors
        direct_candidates = []
        for n in self._neighbors(self.pos):
            nr, nc = n
            status = self.kb.status[nr][nc]
            if status == VISITED:
                continue   # skip — no progress

            if status in (CONFIRMED_PIT, CONFIRMED_WUMPUS):
                risk = 100
            elif status == POSSIBLE_DANGER:
                risk = 80
            elif status == POSSIBLE_PIT:
                risk = 60
            elif status == POSSIBLE_WUMPUS:
                risk = 50 if self.kb.wumpus_alive else 0
            elif status == UNKNOWN:
                risk = 30
            elif status == SAFE:
                risk = 0
            else:
                risk = 0
            direct_candidates.append((risk, n, status))

        direct_candidates.sort(key=lambda x: x[0])

        if direct_candidates:
            best_risk, best_tile, best_status = direct_candidates[0]
            needed_dir = self._direction_to(self.pos, best_tile)

            if needed_dir is not None:
                turns = self._turns_to_face(self.direction, needed_dir)
                self.plan = turns + [MOVE_FORWARD]
                action = self.plan.pop(0)
                thought = (
                    "No safe tiles left. Taking a risk — moving toward {} "
                    "(status: {}, risk: {})."
                    .format(best_tile, best_status, best_risk)
                )
                return (action, thought)

        # Second try: navigate via visited/safe tiles to the nearest
        # unvisited tile anywhere on the grid.
        all_unvisited = set()
        for r in range(self.rows):
            for c in range(self.cols):
                if self.kb.status[r][c] != VISITED:
                    all_unvisited.add((r, c))

        if all_unvisited:
            # Sort by risk, then distance
            scored = []
            for t in all_unvisited:
                tr, tc = t
                s = self.kb.status[tr][tc]
                if s in (CONFIRMED_PIT, CONFIRMED_WUMPUS):
                    risk = 100
                elif s == POSSIBLE_DANGER:
                    risk = 80
                elif s == POSSIBLE_PIT:
                    risk = 60
                elif s == POSSIBLE_WUMPUS:
                    risk = 50 if self.kb.wumpus_alive else 0
                else:
                    risk = 30
                dist = abs(tr - self.pos[0]) + abs(tc - self.pos[1])
                scored.append((risk, dist, t, s))
            scored.sort()

            for _, _, target, target_status in scored:
                # Find a visited neighbor of the target to navigate to,
                # then step into the target from there.
                approach_tiles = [
                    n for n in self._neighbors(target)
                    if self.kb.status[n[0]][n[1]] in (VISITED, SAFE)
                ]
                for approach in approach_tiles:
                    if approach == self.pos:
                        # Already adjacent — just go
                        needed_dir = self._direction_to(self.pos, target)
                        if needed_dir is not None:
                            turns = self._turns_to_face(self.direction, needed_dir)
                            self.plan = turns + [MOVE_FORWARD]
                            action = self.plan.pop(0)
                            thought = (
                                "Navigating to risky tile {} "
                                "(status: {}) — already adjacent."
                                .format(target, target_status)
                            )
                            return (action, thought)

                    path = _astar(
                        start=self.pos,
                        goal=approach,
                        walkable_fn=lambda p: self.kb.is_safe(p),
                        neighbors_fn=self._neighbors,
                    )
                    if path and len(path) > 1:
                        # Navigate to the approach tile, then add one
                        # more MOVE to enter the risky target.
                        full_path = path + [target]
                        self.path = full_path
                        self.plan = self._plan_path_actions(full_path)
                        if self.plan:
                            action = self.plan.pop(0)
                            thought = (
                                "No safe tiles left. Navigating to {} "
                                "(status: {}) via safe path."
                                .format(target, target_status)
                            )
                            return (action, thought)

        # Absolute fallback (shouldn't reach here normally)
        thought = "Completely stuck. Turning randomly as last resort."
        return (TURN_LEFT, thought)

    # ------------------------------------------------------------------
    # Shooting helpers
    # ------------------------------------------------------------------

    def _try_shoot_wumpus(self, wumpus_pos):
        """
        If the agent can shoot the wumpus from the current position
        (same row or column), return (action, thought). Otherwise None.
        """
        wr, wc = wumpus_pos
        ar, ac = self.pos

        shoot_dir = None
        if ar == wr:
            shoot_dir = EAST if wc > ac else WEST
        elif ac == wc:
            shoot_dir = SOUTH if wr > ar else NORTH

        if shoot_dir is not None:
            turns = self._turns_to_face(self.direction, shoot_dir)
            if turns:
                self.plan = turns + [SHOOT]
                action = self.plan.pop(0)
                thought = (
                    "Wumpus confirmed at {}! Turning to shoot."
                    .format(wumpus_pos)
                )
                return (action, thought)
            else:
                thought = (
                    "Wumpus confirmed at {}! Firing arrow {}"
                    .format(wumpus_pos, DIRECTION_NAMES[shoot_dir])
                )
                return (SHOOT, thought)

        return None

    def _try_shoot_suspected_wumpus(self):
        """
        Find any POSSIBLE_WUMPUS tile and try to navigate to a
        position where we can shoot it.  Returns (action, thought)
        or None.
        """
        for r in range(self.rows):
            for c in range(self.cols):
                if self.kb.status[r][c] not in (POSSIBLE_WUMPUS, CONFIRMED_WUMPUS):
                    continue

                ar, ac = self.pos

                # Can we shoot from here?
                shoot_dir = None
                if ar == r:
                    shoot_dir = EAST if c > ac else WEST
                elif ac == c:
                    shoot_dir = SOUTH if r > ar else NORTH

                if shoot_dir is not None:
                    turns = self._turns_to_face(self.direction, shoot_dir)
                    self.plan = turns + [SHOOT]
                    action = self.plan.pop(0)
                    thought = (
                        "No safe tiles available. Wumpus suspected at "
                        "({}, {}). Attempting to shoot."
                        .format(r, c)
                    )
                    return (action, thought)

                # Can't shoot from here — try navigating to a tile on the
                # same row or column as the suspect, via safe/visited tiles.
                firing_positions = []
                for fr in range(self.rows):
                    for fc in range(self.cols):
                        if (fr, fc) == (r, c):
                            continue
                        if fr == r or fc == c:
                            if self.kb.is_safe((fr, fc)):
                                firing_positions.append((fr, fc))

                if firing_positions:
                    result = self._plan_to_nearest(set(firing_positions))
                    if result is not None:
                        return result

        return None
