"""
game.py — Game loop and scoring engine for Wumpus World

Orchestrates the interaction between World, Agent, and UI.
Each turn: World emits percepts → Agent decides → Game applies action.
The game ends on death, gold grab, wumpus kill, or step timeout.
"""

from world import DIRECTION_NAMES
from agent import MOVE_FORWARD, TURN_LEFT, TURN_RIGHT, GRAB, SHOOT
import ui


# ---------------------------------------------------------------------------
# Scoring constants
# ---------------------------------------------------------------------------
SCORE_ACTION     = -1       # cost per action (move, turn, grab, shoot)
SCORE_SHOOT_MISS = -10      # extra penalty for wasting the arrow
SCORE_WIN        = 1000     # bonus for grabbing gold or killing wumpus
SCORE_DEATH      = -1000    # penalty for dying


class Game:
    """
    Runs a complete Wumpus World game session.

    Attributes
    ----------
    world : World
        The world the agent plays in.
    agent : Agent
        The agent (DumbAgent or SmartAgent).
    max_steps : int
        Safety cap to prevent infinite loops.
    score : int
        Running total score.
    step_count : int
        Number of actions taken so far.
    status : str or None
        "WIN", "LOSE", "TIMEOUT", or None if still running.
    """

    def __init__(self, world, agent, max_steps=100):
        self.world     = world
        self.agent     = agent
        self.max_steps = max_steps
        self.score     = 0
        self.step_count = 0
        self.status    = None

        # Track bump and scream state for the current turn
        self._just_bumped    = False
        self._scream_heard   = False

    # ------------------------------------------------------------------
    # Main game loop
    # ------------------------------------------------------------------

    def run(self):
        """
        Execute the game loop until a terminal condition is reached.
        Returns a dict with 'status', 'score', and 'steps'.
        """

        while self.status is None:

            # ---- 1. Get percepts ----
            percepts = self.world.get_percepts(
                self.agent.pos,
                just_bumped=self._just_bumped,
                scream_heard=self._scream_heard,
            )
            # Reset one-shot flags
            self._just_bumped  = False
            self._scream_heard = False

            # ---- 2. Agent decides ----
            action, thought = self.agent.decide(percepts, self.world)

            # ---- 3. Apply action ----
            self.step_count += 1
            self.score += SCORE_ACTION      # every action costs 1 point

            self._apply_action(action)

            # ---- 4. Render step ----
            ui.render_step_log(
                step_num=self.step_count,
                agent_pos=self.agent.pos,
                agent_dir=self.agent.direction,
                percepts=percepts,
                thought=thought,
                action=action,
                score=self.score,
            )
            ui.render_grid(
                rows=self.world.rows,
                cols=self.world.cols,
                agent_pos=self.agent.pos,
                agent_dir=self.agent.direction,
                visited=self.agent.visited,
                wumpus_pos=self.world.wumpus_pos,
                pit_positions=self.world.pit_positions,
                gold_pos=self.world.gold_pos,
                is_wumpus_alive=self.world.is_wumpus_alive,
                reveal_all=False,
            )

            # ---- 5. Check terminal conditions ----
            self._check_end_conditions()

            # ---- 6. Max steps safety cap ----
            if self.status is None and self.step_count >= self.max_steps:
                self.status = "TIMEOUT"

        # ---- Game over — show final state ----
        ui.render_game_over(
            status=self.status,
            score=self.score,
            steps=self.step_count,
            agent_pos=self.agent.pos,
            agent_dir=self.agent.direction,
            rows=self.world.rows,
            cols=self.world.cols,
            visited=self.agent.visited,
            wumpus_pos=self.world.wumpus_pos,
            pit_positions=self.world.pit_positions,
            gold_pos=self.world.gold_pos,
            is_wumpus_alive=self.world.is_wumpus_alive,
        )

        return {
            "status": self.status,
            "score":  self.score,
            "steps":  self.step_count,
        }

    # ------------------------------------------------------------------
    # Action handlers
    # ------------------------------------------------------------------

    def _apply_action(self, action):
        """Execute a single action and update world/agent state."""

        if action == MOVE_FORWARD:
            new_pos = self.agent.get_forward_pos()
            if self.world.is_valid(new_pos):
                self.agent.pos = new_pos
                self.agent.visited.add(new_pos)
            else:
                # Bump into wall — agent stays in place
                self._just_bumped = True

        elif action == TURN_LEFT:
            self.agent.do_turn_left()

        elif action == TURN_RIGHT:
            self.agent.do_turn_right()

        elif action == GRAB:
            if self.agent.pos == self.world.gold_pos:
                self.agent.has_gold = True

        elif action == SHOOT:
            if self.agent.has_arrow:
                self.agent.has_arrow = False
                hit = self.world.resolve_arrow(
                    self.agent.pos, self.agent.direction
                )
                if hit:
                    self._scream_heard = True
                    self.score += SCORE_WIN      # killing wumpus is a win
                else:
                    self.score += SCORE_SHOOT_MISS

    # ------------------------------------------------------------------
    # End condition checks
    # ------------------------------------------------------------------

    def _check_end_conditions(self):
        """Check if the game should end this turn."""

        pos = self.agent.pos

        # Death by Wumpus
        if (pos == self.world.wumpus_pos and self.world.is_wumpus_alive):
            self.agent.is_alive = False
            self.score += SCORE_DEATH
            self.status = "LOSE"
            return

        # Death by Pit
        if pos in self.world.pit_positions:
            self.agent.is_alive = False
            self.score += SCORE_DEATH
            self.status = "LOSE"
            return

        # Win by grabbing gold
        if self.agent.has_gold:
            self.score += SCORE_WIN
            self.status = "WIN"
            return

        # Win by killing Wumpus (checked after shoot action resolves scream)
        if self._scream_heard:
            self.status = "WIN"
            return
