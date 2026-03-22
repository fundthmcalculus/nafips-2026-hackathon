# -*- coding: utf-8 -*-
# Copyright © 2022 Thales. All Rights Reserved.
# NOTICE: This file is subject to the license agreement defined in file 'LICENSE', which is part of
# this source code package.
import os
import sys

from MyAIController.logic_controller import LogicController
from MyAIController.logic_controller05 import LogicController05

sys.path.append('.')

from kesslergame import KesslerGame, GraphicsType
from Scenarios.example_scenarios import *
from Scenarios.custom_scenarios import custom_scenarios

# Define game scenario
# Run all scenarios and collect statistics
all_results = []

# Disable graphics for faster execution across all scenarios
game_settings = {'perf_tracker': True,
                 'graphics_type': GraphicsType.NoGraphics if not os.getenv('SHOW_GAME') else GraphicsType.Tkinter,  # Change to GraphicsType.Tkinter to visualize
                 'realtime_multiplier': 1,
                 'graphics_obj': None,
                 'frequency': 60}

game = KesslerGame(settings=game_settings)

print("=" * 80)
print("RUNNING ALL SCENARIOS")
print("=" * 80)

for scenario_idx, scenario in enumerate(custom_scenarios):
    print(f"\n{'=' * 80}")
    print(f"SCENARIO {scenario_idx}: {scenario.name}")
    print(f"{'=' * 80}")

    controllers = [LogicController() if state.get('team', 0) == 1 else LogicController05() for state in
                   scenario.ship_states]

    for ij in range(2):
        # Evaluate the game
        pre = time.perf_counter()
        p01 = scenario.ship_states[0]['position']
        p02 = scenario.ship_states[1]['position']
        if ij == 1:
            scenario.ship_states[0]['position'] = p02
            scenario.ship_states[1]['position'] = p01
        score, perf_data = game.run(scenario=scenario, controllers=controllers)
        elapsed = time.perf_counter() - pre
        if ij == 1:
            scenario.ship_states[0]['position'] = p01
            scenario.ship_states[1]['position'] = p02

        # Store results
        result = {
            'scenario_idx': scenario_idx,
            'scenario_name': scenario.name,
            'eval_time': elapsed,
            'stop_reason': score.stop_reason,
            'asteroids_hit': [team.asteroids_hit for team in score.teams],
            'deaths': [team.deaths for team in score.teams],
            'accuracy': [team.accuracy for team in score.teams],
            'mean_eval_time': [team.mean_eval_time for team in score.teams if team is not None]
        }
        all_results.append(result)

        # Print individual scenario results
        print(f'Scenario eval time: {elapsed:.2f}s')
        print(f'Stop reason: {score.stop_reason}')
        print(f'Asteroids hit: {result["asteroids_hit"]}')
        print(f'Deaths: {result["deaths"]}')
        print(f'Accuracy: {result["accuracy"]}')
        print(f'Mean eval time: {result["mean_eval_time"]}')

        # Determine winner based on asteroids hit
        if len(result["asteroids_hit"]) >= 2:
            asteroids_team1 = result["asteroids_hit"][0]
            asteroids_team2 = result["asteroids_hit"][1]
            if asteroids_team1 > asteroids_team2:
                print(f'Winner: {controllers[0].name} (Team 1) with {asteroids_team1} asteroids hit vs {asteroids_team2}')
            elif asteroids_team2 > asteroids_team1:
                print(f'Winner: {controllers[1].name} (Team 2) with {asteroids_team2} asteroids hit vs {asteroids_team1}')
            else:
                print(f'Tie: Both teams hit {asteroids_team1} asteroids')
        else:
            print('Winner: Unable to determine (insufficient teams)')

# Print aggregate statistics
print(f"\n{'=' * 80}")
print("AGGREGATE STATISTICS ACROSS ALL SCENARIOS")
print(f"{'=' * 80}")

total_asteroids_team1 = sum(r['asteroids_hit'][0] for r in all_results)
total_asteroids_team2 = sum(r['asteroids_hit'][1] for r in all_results)
total_deaths_team1 = sum(r['deaths'][0] for r in all_results)
total_deaths_team2 = sum(r['deaths'][1] for r in all_results)
avg_accuracy_team1 = sum(r['accuracy'][0] for r in all_results) / len(all_results)
avg_accuracy_team2 = sum(r['accuracy'][1] for r in all_results) / len(all_results)
total_time = sum(r['eval_time'] for r in all_results)

print(f"Total scenarios run: {len(all_results)}")
print(
    f"Team 1 ({controllers[0].name}) - Total asteroids hit: {total_asteroids_team1}, Total deaths: {total_deaths_team1}, Average accuracy: {avg_accuracy_team1:.2%}")
print(
    f"Team 2 ({controllers[1].name}) - Total asteroids hit: {total_asteroids_team2}, Total deaths: {total_deaths_team2}, Average accuracy: {avg_accuracy_team2:.2%}")
print(f"Total evaluation time: {total_time:.2f}s")

if total_asteroids_team1 > total_asteroids_team2:
    print(
        f"\nOverall Winner: Team 1 ({controllers[0].name}) with {total_asteroids_team1} asteroids hit vs {total_asteroids_team2}")
elif total_asteroids_team2 > total_asteroids_team1:
    print(
        f"\nOverall Winner: Team 2 ({controllers[1].name}) with {total_asteroids_team2} asteroids hit vs {total_asteroids_team1}")
else:
    print(f"\nOverall Tie: Both teams hit {total_asteroids_team1} asteroids")

print(f"\nPer-scenario summary:")
for r in all_results:
    print(
        f"  {r['scenario_name']:20s} - Asteroids: {r['asteroids_hit'][0]:3d}, Deaths: {r['deaths'][0]}, Accuracy: {r['accuracy'][0]:.2%}")
