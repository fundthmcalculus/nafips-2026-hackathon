from kesslergame import Scenario
import numpy as np

def create_incoming_field_scenario():
    """
    Scenario 1: Starting in the middle of a field of asteroids that are all moving in on my position
    """
    map_size = (1000, 800)
    ship_pos = (500, 400)
    asteroid_states = []
    
    # Create a circle of asteroids moving towards the center
    num_asteroids = 12
    radius = 350
    for i in range(num_asteroids):
        angle_deg = i * (360 / num_asteroids)
        angle_rad = np.radians(angle_deg)
        # Position on the circle
        x = ship_pos[0] + radius * np.cos(angle_rad)
        y = ship_pos[1] + radius * np.sin(angle_rad)
        # Velocity angle points towards the ship (opposite to position angle)
        vel_angle = (angle_deg + 180) % 360
        asteroid_states.append({
            'position': (x, y),
            'angle': vel_angle,
            'speed': 80,
            'size': 3
        })
        
    return Scenario(name='Incoming Field',
                    asteroid_states=asteroid_states,
                    ship_states=[{'position': ship_pos, 'angle': 90, 'lives': 3, 'team': 1}],
                    map_size=map_size,
                    time_limit=60)

def create_zigzag_scenario():
    """
    Scenario 2: A progressively moving left-right field of asteroids with a zig-zag clear path
    """
    map_size = (1000, 800)
    asteroid_states = []
    
    # Fill the screen with asteroids except for a zig-zag path
    # Let's say the ship starts at bottom and needs to go to top
    # Asteroids move left/right
    
    rows = 10
    cols = 12
    x_step = map_size[0] / cols
    y_step = map_size[1] / rows
    
    for r in range(rows):
        # Zig-zag path: clear one or two columns per row
        # Row 0: clear col 1,2
        # Row 1: clear col 2,3
        # Row 2: clear col 3,4
        # ...
        path_col = (r % cols)
        
        for c in range(cols):
            if c != path_col and c != (path_col + 1) % cols:
                x = c * x_step + x_step/2
                y = r * y_step + y_step/2
                # Alternate movement direction per row
                angle = 0 if r % 2 == 0 else 180
                asteroid_states.append({
                    'position': (x, y),
                    'angle': angle,
                    'speed': 50,
                    'size': 2
                })
                
    return Scenario(name='Zig-Zag Path',
                    asteroid_states=asteroid_states,
                    ship_states=[{'position': (500, 50), 'angle': 90, 'lives': 3, 'team': 1}],
                    map_size=map_size,
                    time_limit=60)

def create_crossing_lines_scenario():
    """
    Scenario 3: A line of asteroids at the top and bottom of the screen which move through each other
    """
    map_size = (1000, 800)
    asteroid_states = []
    
    num_per_line = 10
    x_step = map_size[0] / num_per_line
    
    # Top line moving down
    for i in range(num_per_line):
        asteroid_states.append({
            'position': (i * x_step + x_step/2, 100),
            'angle': 90, # Down is 90 if we follow standard kesslergame (y increases down?)
            # Wait, kesslergame uses standard math coordinates often, but let's check.
            # In asteroid.py: vx = speed * cos(rad), vy = speed * sin(rad)
            # y = (y + vy * dt) % height.
            # So if vy > 0, y increases. In many engines (0,0) is top-left, so vy > 0 is down.
            # Let's use 90 for down, 270 for up.
            'speed': 100,
            'size': 3
        })
        
    # Bottom line moving up
    for i in range(num_per_line):
        asteroid_states.append({
            'position': (i * x_step + x_step/2, 700),
            'angle': 270,
            'speed': 100,
            'size': 3
        })
        
    return Scenario(name='Crossing Lines',
                    asteroid_states=asteroid_states,
                    ship_states=[{'position': (500, 400), 'angle': 0, 'lives': 3, 'team': 1}],
                    map_size=map_size,
                    time_limit=60)

def create_closing_walls_scenario():
    """
    Scenario 4: A line of asteroids on each side of the screen, the middle of the screen, and the outside ones move in.
    """
    map_size = (1000, 800)
    asteroid_states = []
    
    num_per_line = 8
    y_step = map_size[1] / num_per_line
    
    # Left wall moving right
    for i in range(num_per_line):
        asteroid_states.append({
            'position': (100, i * y_step + y_step/2),
            'angle': 0,
            'speed': 60,
            'size': 3
        })
        
    # Right wall moving left
    for i in range(num_per_line):
        asteroid_states.append({
            'position': (900, i * y_step + y_step/2),
            'angle': 180,
            'speed': 60,
            'size': 3
        })
        
    # Middle wall stationary (or slow)
    for i in range(num_per_line):
        asteroid_states.append({
            'position': (500, i * y_step + y_step/2),
            'angle': 0,
            'speed': 0,
            'size': 3
        })
        
    return Scenario(name='Closing Walls',
                    asteroid_states=asteroid_states,
                    ship_states=[{'position': (300, 400), 'angle': 90, 'lives': 3, 'team': 1}],
                    map_size=map_size,
                    time_limit=60)

def create_ram_scenario():
    """
    Scenario for testing ramming: Two ships, one with fewer lives than the other, starting close together.
    """
    map_size = (1000, 800)
    ship_pos_1 = (400, 400)
    ship_pos_2 = (600, 400)
    
    # Needs at least one asteroid to be valid
    asteroid_states = [{
        'position': (900, 700),
        'angle': 0,
        'speed': 0,
        'size': 1
    }]
    
    return Scenario(name='Ramming Test',
                    asteroid_states=asteroid_states,
                    ship_states=[
                        {'position': ship_pos_1, 'angle': 0, 'lives': 3, 'team': 1},
                        {'position': ship_pos_2, 'angle': 180, 'lives': 1, 'team': 2}
                    ],
                    map_size=map_size,
                    time_limit=30)

incoming_field = create_incoming_field_scenario()
zigzag_path = create_zigzag_scenario()
crossing_lines = create_crossing_lines_scenario()
closing_walls = create_closing_walls_scenario()
ramming_test = create_ram_scenario()

custom_scenarios = [incoming_field, zigzag_path, crossing_lines, closing_walls, ramming_test]
