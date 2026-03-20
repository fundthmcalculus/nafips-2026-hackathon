# -*- coding: utf-8 -*-
# Copyright © 2022 Thales. All Rights Reserved.
# NOTICE: This file is subject to the license agreement defined in file 'LICENSE', which is part of
# this source code package.

import sys

from MyAIController.logic_controller import LogicController

sys.path.append('.')

from kesslergame import KesslerGame, GraphicsType
from Scenarios.example_scenarios import *
from Scenarios.custom_scenarios import custom_scenarios

# Define game scenario
# Run all scenarios and collect statistics
all_results = []

# Disable graphics for faster execution across all scenarios
game_settings = {'perf_tracker': True,
                 'graphics_type': GraphicsType.Tkinter,  # Change to GraphicsType.Tkinter to visualize
                 'realtime_multiplier': 10,
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

    # Evaluate the game
    pre = time.perf_counter()
    controllers = [LogicController() for _ in scenario.ship_states]
    score, perf_data = game.run(scenario=scenario, controllers=controllers)
    elapsed = time.perf_counter() - pre

    # Store results
    result = {
        'scenario_idx': scenario_idx,
        'scenario_name': scenario.name,
        'eval_time': elapsed,
        'stop_reason': score.stop_reason,
        'asteroids_hit': [team.asteroids_hit for team in score.teams],
        'deaths': [team.deaths for team in score.teams],
        'accuracy': [team.accuracy for team in score.teams],
        'mean_eval_time': [team.mean_eval_time for team in score.teams]
    }
    all_results.append(result)

    # Print individual scenario results
    print(f'Scenario eval time: {elapsed:.2f}s')
    print(f'Stop reason: {score.stop_reason}')
    print(f'Asteroids hit: {result["asteroids_hit"]}')
    print(f'Deaths: {result["deaths"]}')
    print(f'Accuracy: {result["accuracy"]}')
    print(f'Mean eval time: {result["mean_eval_time"]}')

# Print aggregate statistics
print(f"\n{'=' * 80}")
print("AGGREGATE STATISTICS ACROSS ALL SCENARIOS")
print(f"{'=' * 80}")

total_asteroids = sum(r['asteroids_hit'][0] for r in all_results)
total_deaths = sum(r['deaths'][0] for r in all_results)
avg_accuracy = sum(r['accuracy'][0] for r in all_results) / len(all_results)
total_time = sum(r['eval_time'] for r in all_results)

print(f"Total scenarios run: {len(all_results)}")
print(f"Total asteroids hit: {total_asteroids}")
print(f"Total deaths: {total_deaths}")
print(f"Average accuracy: {avg_accuracy:.2%}")
print(f"Total evaluation time: {total_time:.2f}s")
print(f"\nPer-scenario summary:")
for r in all_results:
    print(
        f"  {r['scenario_name']:20s} - Asteroids: {r['asteroids_hit'][0]:3d}, Deaths: {r['deaths'][0]}, Accuracy: {r['accuracy'][0]:.2%}")
