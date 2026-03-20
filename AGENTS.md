# AGENTS.md - Developer Guide for NAFIPS 2026 Hackathon

This document provides essential information for AI agents working on this asteroid defense game controller codebase.

## Project Overview

This is a **Kessler Game** - an asteroids-style simulation where autonomous ship controllers must navigate, avoid asteroids, destroy asteroids, and compete against other ships. The goal is to develop controllers that maximize mission success through smart decision-making.

### Key Technologies
- Python 3.x
- NumPy for numerical computations
- DEAP (Distributed Evolutionary Algorithms in Python) for genetic algorithm training
- scikit-fuzzy for fuzzy logic controllers
- kesslergame - the underlying game engine

## Project Structure

```
nafips-2026-hackathon/
├── main.py                           # Sample entry point (not used for actual runs)
├── requirements.txt                  # Python dependencies
├── crush.json                        # AI assistant configuration
├── Scripts/                          # Testing and training scripts
│   ├── best_solution.json            # Best GA-generated solution (50 genes)
│   ├── scenario_test_fuzzy.py        # Test multiple scenarios with controllers
│   ├── demo_hacker_controller.py     # Demo HackerController features
│   ├── test_hacker_controller.py     # Tests for hacker controller
│   └── example_*.py                  # Training/fuzzy examples
├── Scenarios/                        # Scenario definitions
│   ├── custom_scenarios.py           # Custom scenarios: incoming_field, zigzag_path, crossing_lines, closing_walls, ramming_test
│   ├── example_scenarios.py          # Basic training scenarios
│   └── example_training_portfolios.py
└── MyAIController/                   # Your AI controllers live here
    ├── logic_controller*.py          # Logic-based controllers (01-04)
    ├── hacker_controller.py          # Cheat/hack-based controller
    ├── sa/                           # Situational Awareness system
    │   ├── sa.py                     # SA class - main entry point
    │   ├── saship.py                 # SAShip and OwnShip classes
    │   ├── saasteroids.py            # SAAsteroid class with wrap-around support
    │   ├── sabullets.py              # SABullet class (minimal)
    │   └── util/helpers.py           # trim_angle() helper function
    ├── example_controller_fuzzy*.py  # Fuzzy logic controllers
    └── __init__.py
```

## Core Concepts

### Situational Awareness (SA) System

The `SA` class (`MyAIController/sa/sa.py`) is your primary interface to game state:

```python
from MyAIController.sa.sa import SA
sa = SA()
sa.update(ship_state, game_state)
```

After update, access:
- `sa.ownship` - Your ship's state (position, velocity, heading, speed, bullets_remaining, etc.)
- `sa.redships` - List of enemy ships
- `sa.metrics` - Environment metrics (avg asteroid size/speed, stddev, etc.)

### Ship State Access

**OwnShip properties:**
- `position` - [x, y] coordinates
- `velocity` - [vx, vy]
- `speed` - Magnitude of velocity
- `heading` - Direction ship is pointing (-180 to 180 degrees)
- `lives` - Remaining lives
- `radius` - Ship radius for collision detection
- `asteroids` - List of SAAsteroid objects relative to your ship
- `bullets_remaining` - Ammo count

**SAAsteroid properties (wrap-around enabled):**
- `position` / `position_wrap` - Absolute vs. wrapped position (closest via map edges)
- `distance` / `distance_wrap` - Distance with/without wrap consideration
- `bearing` / `bearing_wrap` - Bearing from ship (0° = north, clockwise positive)
- `velocity`, `speed`, `heading`
- `size` - 1-4 (larger = more shots needed to destroy)
- `tti` - Time-to-impact (None if no collision course)
- `radius`, `mass`

### Helper Functions

```python
from MyAIController.sa.util.helpers import trim_angle

# Trims angle to (-180, 180] range
angle = trim_angle(270)  # Returns -90
```

## Controller Interface

All controllers inherit from `KesslerController` and implement:

```python
def actions(self, ship_state: Dict, game_state: GameState) -> Tuple[float, float, bool, bool]:
    """
    Returns:
        thrust: Thrust value (min to max, typically -480 to +480)
        turn_rate: Turn rate (typically -180 to +180 deg/s)
        fire: True to shoot bullet
        drop_mine: True to lay mine
    """
```

**Return format:** `(thrust: float, turn_rate: float, fire: bool, drop_mine: bool)`

### Key Constants

From the codebase observations:
- Map size: (1000, 800) typically
- Max thrust: ~480 m/s² acceleration (ship_state['thrust_range'][1] gives max)
- Max turn rate: ~180 deg/s
- Bullet speed: ~2200 units/s
- Ship mass: 300.0
- Asteroid sizes 1-4 require 1, 4, 13, 40 shots respectively to destroy

## Controller Patterns

### Logic Controllers (`logic_controller*.py`)

The `LogicController04` is the most advanced logic-based controller with:

**Threat Assessment:**
- Calculates time-to-closest-approach for each asteroid
- Prioritizes asteroids on collision course
- Uses threat scoring based on distance, relative angle, size

**Intercept Calculation:**
```python
intercept_x, intercept_y, time_to_intercept = calculate_intercept_point(asteroid)
```
Solves quadratic equation to find bullet-asteroid intersection point.

**Emergency Escape:**
When respawning and too close to an asteroid:
1. Finds safe escape target within 3 seconds
2. Uses full thrust away from danger
3. Disables shooting during escape

### Hacker Controller (`hacker_controller.py`)

A "cheat" controller that modifies game state directly via memory reflection:

**Hacks available:**
- `update_score()` - Sets own team 1 point ahead of competition
- `instant_turn()` - Forces ship heading instantly (bypasses turn rate limits)
- `teleport_ship()` - Randomly repositions ship
- `teleport_and_shoot()` - Teleports behind asteroid, aims, and shoots
- `deposit_mine_ahead_of_opponent()` - Places mines in opponent's path
- `tractor_beam()` - Pulls/pushes targets via velocity modification
- `update_bullet_colors()` - Changes bullet colors to rainbow
- `apply_nyan_cat()` / `clown_face()` - Swaps ship sprites
- `apply_turd_mines()` - Replaces mine sprites with turd images
- `shotgun_blast()` - Spawns mines in asteroid clusters

**Access pattern:**
```python
run_locals = self.find_game_elements()  # Gets game state from memory
# Modify ships, asteroids, mines in run_locals dict
```

### Fuzzy Controllers (`example_controller_fuzzy.py`)

Uses DEAP genetic algorithm to evolve fuzzy inference systems:

**Evolution setup (from `example_fuzzy_training_script.py`):**
```python
creator.create("FitnessMax", base.Fitness, weights=(1.0,))
creator.create("Individual", list, fitness=creator.FitnessMax)
toolbox.register("individual", tools.initRepeat, creator.Individual,
                 toolbox.attr_flt1, 50)  # 50 gene chromosome
```

**Chromosome structure (50 floats):**
- Genes 0-49 encode membership function boundaries and rule consequents
- Use `self.chromosome` parameter in constructor to load evolved values

## Testing & Training Commands

### Run a Single Game (with graphics)

```bash
python -m Scripts.demo_hacker_controller
```

Settings from demo:
```python
game_settings = {
    'perf_tracker': True,
    'graphics_type': GraphicsType.Tkinter,  # Use NoGraphics for speed
    'realtime_multiplier': 0.7,
    'frequency': 30
}
```

### Run Multiple Scenarios (no graphics - for testing)

```bash
python Scripts/scenario_test_fuzzy.py
```

This runs all `custom_scenarios` with both controllers and reports aggregate statistics.

### Train with Genetic Algorithm

```bash
python Scripts/example_fuzzy_training_script.py
```

**GA parameters:**
- Population size: 20
- Generations: 1000 (stop condition)
- Crossover probability: 0.5
- Mutation probability: 0.2 (Gaussian mutation, σ=0.2)

**Best solution:** See `Scripts/best_solution.json` (generation 9, fitness ~2.20)

### Custom Scenario Testing

```python
from kesslergame import KesslerGame, Scenario, GraphicsType

scenario = Scenario(
    name='MyTest',
    num_asteroids=10,
    ship_states=[
        {'position': (400, 400), 'angle': 90, 'lives': 3, 'team': 1},
        {'position': (600, 600), 'angle': 90, 'lives': 3, 'team': 2}
    ],
    map_size=(1000, 800),
    time_limit=30
)

game = KesslerGame(settings={
    'graphics_type': GraphicsType.NoGraphics,
    'realtime_multiplier': 1.0
})
score, perf_data = game.run(scenario=scenario, controllers=[MyController(), OtherController()])
```

## Key Gotchas & Non-Obvious Patterns

### 1. Angle Conventions (CRITICAL)

**Kessler Game uses:**
- Angles in degrees
- 0° = UP (north), 90° = RIGHT, -90° = LEFT, 180/180 = DOWN
- Positive angles rotate clockwise

**Controller code consistently adjusts by -90°:**
```python
self.heading = trim_angle(ship_dict['heading'] - 90)  # saship.py line 45
```

This means internal calculations use:
- Heading 0 = UP in game state → becomes -90 internally (pointing right)
- So internal 0° points RIGHT along +x axis

**Always use `trim_angle()` to normalize angles.**

### 2. Map Wrap-Around

Asteroids can appear on opposite sides of map when close to edge. Always use:
- `distance_wrap` / `bearing_wrap` instead of raw `distance` / `bearing`
- `position_wrap` for position calculations

Wrap-around handling:
```python
if abs(dx) > map_width / 2:
    dx = dx - np.sign(dx) * map_width
```

### 3. Bullet Velocity Model

Bullets inherit ship velocity:
```
bullet_velocity = ship_velocity + bullet_speed * [cos(heading), sin(heading)]
```

This must be accounted for in intercept calculations (see `calculate_intercept_point`).

### 4. Response Time Limitations

- Game runs at ~30 Hz (frequency setting)
- Controllers have limited eval time per frame
- LogicController04 limits max speed to 40 units/s to allow more reaction time

### 5. Mine Mechanics

- Mines explode after fuse_time (default 3.0 seconds)
- Blast radius causes damage
- `drop_mine` returns True to lay one
- Ships have limited mines: `"mines_remaining": 3` in ship_state

## Code Style & Patterns

### Imports
All controller files use:
```python
from typing import Dict, Tuple
import numpy as np
from kesslergame import KesslerController
```

### Property-Based Helper Access
The SA system uses property decorators to cache expensive calculations:

```python
@property
def distance_wrap(self):
    if self._distance_wrap:
        return self._distance_wrap
    else:
        # Calculate, save, and return
        ...
```

Access: `asteroid.distance_wrap` (not `asteroid.distance_wrap()`)

### Naming Conventions

- Classes: CamelCase (LogicController, SAAsteroid, OwnShip)
- Methods/variables: snake_case (get_most_threatening_asteroid, ship_state)
- Constants: UPPER_CASE (MAX_THRUST if defined)

## Important Files to Reference

| File | Purpose |
|------|---------|
| `MyAIController/logic_controller04.py` | Best logic-based controller implementation |
| `MyAIController/sa/sa.py` | Main SA class - your primary interface |
| `MyAIController/sa/util/helpers.py` | Helper functions (trim_angle) |
| `MyAIController/sa/saship.py` | Ship state model classes |
| `Scripts/best_solution.json` | Example chromosome for fuzzy controller |

## Common Tasks

### Add a New Controller

1. Create file in `MyAIController/`
2. Import: `from kesslergame import KesslerController`
3. Extend class: `class MyController(KesslerController)`
4. Implement `actions()` method
5. Register in test script:

```python
controllers = [LogicController04(), MyNewController()]
score, perf_data = game.run(scenario=scenario, controllers=controllers)
```

### Access Enemy Ships

```python
for red_ship in self.sa.redships:
    dx = red_ship.position[0] - self.sa.ownship.position[0]
    dy = red_ship.position[1] - self.sa.ownship.position[1]
    dist = np.sqrt(dx**2 + dy**2)
```

### Get Nearest Asteroid

```python
nearest = self.sa.ownship.nearest_n(1)[0]
# Or with wrap-around consideration:
nearest_wrap = self.sa.ownship.nearest_n_wrap(1)[0]
```

### Check for Imminent Collision

```python
for asteroid in self.sa.ownship.asteroids:
    if asteroid.tti is not None and 0 < asteroid.tti < 5.0:
        # Will collide within 5 seconds!
```

## Dependencies (from requirements.txt)

| Package | Use |
|---------|-----|
| numpy | Numerical operations, trig, arrays |
| scikit-fuzzy | Fuzzy logic controllers |
| deap | Genetic algorithm framework |
| scipy | Scientific computing |
| matplotlib | Plotting/visualization |
| pandas | Data handling |
| joblib | Caching |
| kesslergame | Game engine |

## Testing Workflow

1. **Quick test** (no graphics, 2 scenarios):
   ```bash
   python Scripts/scenario_test_fuzzy.py
   ```

2. **Debug with visuals:**
   ```python
   'graphics_type': GraphicsType.Tkinter,
   'realtime_multiplier': 0.7
   ```

3. **Train fuzzy controller:**
   ```bash
   python Scripts/example_fuzzy_training_script.py
   ```

4. **Test trained controller:**
   - Copy genome from `best_solution.json`
   - Paste into chromosome parameter of MyFuzzyController

## Notes for Future Agents

- The codebase uses a custom SA (Situational Awareness) system rather than raw game_state access
- Map coordinates: (0,0) = top-left, x increases right, y increases down
- Heading convention is inverted from standard mathematical convention (-90° adjustment)
- Always account for map wrap-around when asteroids are near edges
- The HackerController demonstrates how to use Python reflection to modify game state at runtime
- Fuzzy controllers evolve 50-gene chromosomes that define membership functions and rules
- Logic controllers prioritize survival (avoid collisions) over score maximization
