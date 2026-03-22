import sys
import os

# from ScottDickController.scott_dick_controller import ScottDickController

# Add the project root to sys.path
sys.path.append(os.getcwd())

from kesslergame import Scenario, KesslerGame, GraphicsType
from MyAIController.hacker_controller import HackerController
from MyAIController.logic_controller import LogicController

# Define game scenario
my_test_scenario = Scenario(name='Hacker Test Scenario',
                            num_asteroids=10,
                            ship_states=[
                                {'position': (400, 400), 'angle': 90, 'lives': 3, 'team': 1, "mines_remaining": 3},
                                {'position': (600, 600), 'angle': 90, 'lives': 3, 'team': 2, "mines_remaining": 3},
                            ],
                            map_size=(1000, 800),
                            time_limit=30,
                            stop_if_no_ammo=False)

# Define Game Settings
game_settings = {'perf_tracker': True,
                 'graphics_type': GraphicsType.Tkinter,
                 'realtime_multiplier': 0.7,
                 'graphics_obj': None,
                 'competition_safe_mode': True,
                 'frequency': 60}

game = KesslerGame(settings=game_settings)

# Evaluate the game
score, perf_data = game.run(scenario=my_test_scenario, controllers=[HackerController(), LogicController()])
# score, perf_data = game.run(scenario=my_test_scenario, controllers=[ScottDickController(), LogicController()])

# Print out some general info about the result
print(f'Stop reason: {score.stop_reason}')
for i, team in enumerate(score.teams):
    print(f'Team {i+1} ({team.team_name}): Asteroids hit: {team.asteroids_hit}, Deaths: {team.deaths}')

# Verify if HackerController (Team 1) is 1 point ahead
hacker_score = score.teams[0].asteroids_hit
other_score = score.teams[1].asteroids_hit
print(f'Hacker Score: {hacker_score}, Other Score: {other_score}')
if hacker_score > other_score:
    print('SUCCESS: Hacker is ahead!')
else:
    print('FAILURE: Hacker is not 1 point ahead.')
