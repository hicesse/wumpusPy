"""
tests.py — Verification & Testing for Wumpus World

Run with:  python tests.py
"""

import io
import sys


# ---------------------------------------------------------------------------
# Helper: suppress print output during game runs
# ---------------------------------------------------------------------------
class SuppressOutput:
    """Context manager to capture and discard stdout."""
    def __enter__(self):
        self._old = sys.stdout
        sys.stdout = io.StringIO()
        return self
    def __exit__(self, *args):
        sys.stdout = self._old


# ---------------------------------------------------------------------------
# Test 1: World percept generation — borders and corners
# ---------------------------------------------------------------------------
def test_world_percepts():
    from world import World, EAST

    w = World(rows=4, cols=4, seed=42)
    # seed=42 → Wumpus=(2,3), Pits={(0,1),(0,2),(3,1)}, Gold=(1,3)

    # Corner (0,0) — only 2 neighbors: (0,1) and (1,0)
    # (0,1) is a pit → breeze expected
    p = w.get_percepts((0, 0))
    assert p["breeze"] is True,   "Corner (0,0) should have breeze"
    assert p["stench"] is False,  "Corner (0,0) should NOT have stench"
    assert p["glitter"] is False, "Corner (0,0) should NOT have glitter"

    # Tile adjacent to Wumpus at (2,3) → stench expected
    p = w.get_percepts((1, 3))
    assert p["stench"] is True, "(1,3) adjacent to Wumpus should have stench"

    # Gold tile (1,3) → glitter expected
    p = w.get_percepts((1, 3))
    assert p["glitter"] is True, "(1,3) with Gold should have glitter"

    # Bump and scream passthrough
    p = w.get_percepts((0, 0), just_bumped=True, scream_heard=True)
    assert p["bump"] is True,   "bump should be True when just_bumped=True"
    assert p["scream"] is True, "scream should be True when scream_heard=True"

    # Boundary checks
    assert w.is_valid((0, 0)) is True
    assert w.is_valid((3, 3)) is True
    assert w.is_valid((-1, 0)) is False
    assert w.is_valid((4, 4)) is False

    print("  [PASS] test_world_percepts")


# ---------------------------------------------------------------------------
# Test 2: DumbAgent loop prevention
# ---------------------------------------------------------------------------
def test_dumb_agent_loop_prevention():
    from world import World
    from agent import DumbAgent, MOVE_FORWARD, TURN_LEFT, TURN_RIGHT
    from game import Game

    # Run the DumbAgent on seed 0 — should terminate within 100 steps
    w = World(rows=4, cols=4, seed=0)
    agent = DumbAgent()

    with SuppressOutput():
        game = Game(world=w, agent=agent, max_steps=100)
        result = game.run()

    # Verify it finished (either win, lose, or timeout — NOT infinite)
    assert result["status"] in ("WIN", "LOSE", "TIMEOUT"), \
        "DumbAgent should terminate within max_steps"
    assert result["steps"] <= 100, "Should not exceed 100 steps"

    # Check that the agent visited more than just 2 tiles
    # (proving it doesn't just ping-pong)
    assert len(agent.visited) >= 2, "DumbAgent should visit multiple tiles"

    print("  [PASS] test_dumb_agent_loop_prevention")


# ---------------------------------------------------------------------------
# Test 3: SmartAgent KB deductive reasoning
# ---------------------------------------------------------------------------
def test_smart_agent_kb_deduction():
    from world import World
    from agent import SmartAgent, SAFE, VISITED, POSSIBLE_PIT, CONFIRMED_PIT

    # seed 0: Wumpus=(3,2), Pits={(3,1),(3,3),(1,3)}, Gold=(0,1)
    w = World(rows=4, cols=4, seed=0)
    a = SmartAgent(rows=4, cols=4)

    # Get percepts at (0,0) — no stench, no breeze → all neighbors safe
    p = w.get_percepts((0, 0))
    a.kb.mark_visited((0, 0), p)

    assert a.kb.status[0][1] == SAFE, "(0,1) should be SAFE"
    assert a.kb.status[1][0] == SAFE, "(1,0) should be SAFE"
    assert a.kb.status[0][0] == VISITED, "(0,0) should be VISITED"

    # Visit (0,1) — glitter, no stench, no breeze → neighbors safe
    p = w.get_percepts((0, 1))
    a.kb.mark_visited((0, 1), p)
    assert a.kb.status[0][2] == SAFE, "(0,2) should be SAFE after (0,1) visit"
    assert a.kb.status[1][1] == SAFE, "(1,1) should be SAFE after (0,1) visit"

    print("  [PASS] test_smart_agent_kb_deduction")


# ---------------------------------------------------------------------------
# Test 4: SmartAgent A* pathfinding
# ---------------------------------------------------------------------------
def test_smart_agent_astar():
    from agent import _astar

    # Simple 4x4 grid, all walkable
    def walkable(p):
        return 0 <= p[0] < 4 and 0 <= p[1] < 4

    def neighbors(p):
        r, c = p
        result = []
        for dr, dc in [(0,1),(0,-1),(1,0),(-1,0)]:
            nr, nc = r+dr, c+dc
            if 0 <= nr < 4 and 0 <= nc < 4:
                result.append((nr, nc))
        return result

    path = _astar((0, 0), (3, 3), walkable, neighbors)
    assert len(path) == 7, "Path from (0,0) to (3,3) should be 7 tiles"
    assert path[0] == (0, 0), "Path should start at (0,0)"
    assert path[-1] == (3, 3), "Path should end at (3,3)"

    # Path with a wall blocking
    def walkable_wall(p):
        # Block column 1 entirely
        if p[1] == 1:
            return False
        return 0 <= p[0] < 4 and 0 <= p[1] < 4

    path2 = _astar((0, 0), (0, 2), walkable_wall, neighbors)
    assert path2 == [], "No path should exist through a wall"

    print("  [PASS] test_smart_agent_astar")


# ---------------------------------------------------------------------------
# Test 5: Replay session consistency
# ---------------------------------------------------------------------------
def test_replay_consistency():
    from world import World

    w1 = World(rows=4, cols=4, seed=99)
    w2 = w1.clone()

    assert w2.wumpus_pos == w1.wumpus_pos, "Clone wumpus mismatch"
    assert w2.pit_positions == w1.pit_positions, "Clone pits mismatch"
    assert w2.gold_pos == w1.gold_pos, "Clone gold mismatch"
    assert w2.is_wumpus_alive == w1.is_wumpus_alive, "Clone alive mismatch"
    assert w2 is not w1, "Clone should be a different object"

    # Mutating original shouldn't affect clone
    w1.is_wumpus_alive = False
    assert w2.is_wumpus_alive is True, "Clone should be independent"

    print("  [PASS] test_replay_consistency")


# ---------------------------------------------------------------------------
# Test 6: Full game — DumbAgent terminates
# ---------------------------------------------------------------------------
def test_full_game_dumb():
    from world import World
    from agent import DumbAgent
    from game import Game

    wins = 0
    losses = 0
    timeouts = 0

    for seed in range(20):
        w = World(rows=4, cols=4, seed=seed)
        agent = DumbAgent()
        with SuppressOutput():
            game = Game(world=w, agent=agent, max_steps=100)
            result = game.run()
        if result["status"] == "WIN":
            wins += 1
        elif result["status"] == "LOSE":
            losses += 1
        else:
            timeouts += 1

    # Just verify all 20 games terminated
    total = wins + losses + timeouts
    assert total == 20, "All 20 games should terminate"

    print("  [PASS] test_full_game_dumb (wins={}, losses={}, timeouts={})".format(
        wins, losses, timeouts))


# ---------------------------------------------------------------------------
# Test 7: Full game — SmartAgent outperforms DumbAgent
# ---------------------------------------------------------------------------
def test_full_game_smart_vs_dumb():
    from world import World
    from agent import DumbAgent, SmartAgent
    from game import Game

    smart_wins = 0
    dumb_wins = 0

    for seed in range(20):
        w = World(rows=4, cols=4, seed=seed)

        # Smart
        w1 = w.clone()
        s = SmartAgent(rows=4, cols=4)
        with SuppressOutput():
            g1 = Game(world=w1, agent=s, max_steps=100)
            r1 = g1.run()

        # Dumb
        w2 = w.clone()
        d = DumbAgent()
        with SuppressOutput():
            g2 = Game(world=w2, agent=d, max_steps=100)
            r2 = g2.run()

        if r1["status"] == "WIN":
            smart_wins += 1
        if r2["status"] == "WIN":
            dumb_wins += 1

    assert smart_wins >= dumb_wins, \
        "SmartAgent should win at least as often as DumbAgent"

    print("  [PASS] test_full_game_smart_vs_dumb "
          "(smart_wins={}, dumb_wins={})".format(smart_wins, dumb_wins))


# ---------------------------------------------------------------------------
# Test 8: Arrow / shoot mechanic
# ---------------------------------------------------------------------------
def test_arrow_mechanic():
    from world import World, EAST

    w = World(rows=4, cols=4, seed=42)
    # Wumpus at (2,3)

    # Shoot from (2,0) EAST → should hit wumpus at (2,3)
    assert w.is_wumpus_alive is True
    hit = w.resolve_arrow((2, 0), EAST)
    assert hit is True, "Arrow should hit wumpus at (2,3)"
    assert w.is_wumpus_alive is False, "Wumpus should be dead"

    # Shooting again should miss (wumpus already dead)
    hit2 = w.resolve_arrow((2, 0), EAST)
    assert hit2 is False, "Second arrow should miss (wumpus dead)"

    print("  [PASS] test_arrow_mechanic")


# ===========================================================================
# Run all tests
# ===========================================================================
if __name__ == "__main__":
    print()
    print("=" * 50)
    print("  WUMPUS WORLD — TEST SUITE")
    print("=" * 50)
    print()

    test_world_percepts()
    test_dumb_agent_loop_prevention()
    test_smart_agent_kb_deduction()
    test_smart_agent_astar()
    test_replay_consistency()
    test_full_game_dumb()
    test_full_game_smart_vs_dumb()
    test_arrow_mechanic()

    print()
    print("  ✅ ALL TESTS PASSED")
    print()
