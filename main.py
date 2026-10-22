"""
main.py — Entry point for Wumpus World

Interactive session loop:
  1. Configure grid size
  2. Pick agent mode (Dumb or Smart)
  3. Watch the game run step-by-step
  4. Post-game: replay same world, new world, or exit

All game output is also saved to result.txt (overwritten each session).
"""

from world import World
from agent import DumbAgent, SmartAgent
from game import Game
import ui


def create_agent(mode, rows, cols):
    """Create an agent based on the selected mode."""
    if mode == 2:
        return SmartAgent(rows=rows, cols=cols)
    else:
        return DumbAgent()


def main():
    """Main session loop."""

    # Open result.txt — all game output is mirrored here.
    # The file is overwritten each time the program runs.
    ui.open_result_file()

    try:
        ui.render_banner()

        # ---- Configure grid ----
        rows, cols = ui.prompt_grid_size()
        print()

        # ---- Generate initial world ----
        original_world = World(rows=rows, cols=cols)

        # ---- Session loop ----
        while True:

            # ---- Pick agent mode ----
            mode = ui.prompt_agent_mode()
            mode_name = "Smart Agent (A*)" if mode == 2 else "Dumb Agent"
            print()
            ui._print("  Starting game with {} on a {}x{} grid...".format(
                mode_name, rows, cols
            ))
            ui._print()

            # ---- Clone the world so replays use the same layout ----
            world = original_world.clone()
            agent = create_agent(mode, rows, cols)

            # ---- Run game ----
            game = Game(world=world, agent=agent, max_steps=100)
            result = game.run()

            # ---- Post-game menu ----
            print()
            choice = ui.prompt_post_game()

            if choice == 1:
                # Replay same world — loop back to mode selection
                ui._print("\n  Replaying the same world layout...\n")
                continue

            elif choice == 2:
                # New world
                ui._print("\n  Generating a new random world...\n")
                original_world = World(rows=rows, cols=cols)
                continue

            else:
                # Exit
                ui._print("\n  Thanks for playing Wumpus World! Goodbye.\n")
                break

    finally:
        # Always close the result file, even on error
        ui.close_result_file()


if __name__ == "__main__":
    main()
