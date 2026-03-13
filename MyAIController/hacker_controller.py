import gc
import inspect
import random
import colorsys
import numpy as np
from kesslergame import KesslerController, KesslerGame
from typing import Dict, Tuple

from MyAIController.sa.sa import SA


class HackerController(KesslerController):
    def __init__(self):
        super().__init__()
        self.game_instance = None
        self.own_ship = None
        self.target_heading = None
        self.sa = SA()
        self.hue = 0.0
        self.teleport_counter = 0

    def find_game_elements(self):
        """Find the KesslerGame object and other game elements in memory using Python reflection/GC."""
        # Find the ship instance matching self.ship_id
        if not self.own_ship:
            for obj in gc.get_objects():
                # Check for Ship class (not the ShipState dictionary)
                if hasattr(obj, 'id') and hasattr(obj, 'controller') and obj.id == self.ship_id:
                    self.own_ship = obj
                    break

        # Find the game's run method frame and extract local variables like 'score'
        for frame_info in inspect.stack():
            frame = frame_info.frame
            if 'self' in frame.f_locals and isinstance(frame.f_locals['self'], KesslerGame):
                self.game_instance = frame.f_locals['self']
                return frame.f_locals
        return None

    def update_score(self, run_locals: Dict):
        """Update the score so my ship is always 1 point ahead of the competition."""
        if not run_locals or 'score' not in run_locals:
            return

        score_obj = run_locals['score']
        my_team_id = self.own_ship.team if self.own_ship else None
        
        if my_team_id is None:
            return

        # Find maximum score of other teams
        max_other_score = 0
        my_team_score_obj = None
        for team in score_obj.teams:
            if team.team_id != my_team_id:
                max_other_score = max(max_other_score, team.asteroids_hit)
            else:
                my_team_score_obj = team

        if my_team_score_obj:
            # Keep my ship 1 point ahead of the best competitor
            my_team_score_obj.asteroids_hit = max_other_score + 1
            # Update the asteroids_hit in the Ship object too
            if self.own_ship:
                self.own_ship.asteroids_hit = max_other_score + 1
                
        # Also, to be sure, let's update ALL ships in my team (if there are any)
        if 'ships' in run_locals:
            for ship in run_locals['ships']:
                if ship.team == my_team_id:
                    ship.asteroids_hit = max_other_score + 1

    def instant_turn(self, ship_state: Dict, game_state, run_locals: Dict):
        """Modify the game state so my ship turns instantaneously."""
        # The user wants to modify the game state so the ship turns instantaneously.
        # This can be done by intercepting the actions and directly setting the ship's heading.

        # We need to know the desired heading. Let's say we want to point at the nearest asteroid.
        if not game_state['asteroids']:
            return

        ship_pos = ship_state['position']
        # Find nearest asteroid
        nearest_ast = self.sa.ownship.nearest_n(1)[0]
        # nearest_ast = min(game_state['asteroids'],
        #                  key=lambda a: (a['position'][0]-ship_pos[0])**2 + (a['position'][1]-ship_pos[1])**2)

        import math
        dx = nearest_ast.position[0] - ship_pos[0]
        dy = nearest_ast.position[1] - ship_pos[1]

        # Calculate angle in degrees (kesslergame uses degrees, 0 is up/right?)
        # Actually from logic_controller.py: angle_to_intercept = np.degrees(np.arctan2(dy, dx))-90.0
        target_angle = math.degrees(math.atan2(dy, dx)) - 90.0

        # Set heading directly in the ship object from run_locals
        if run_locals and 'ships' in run_locals:
            for ship in run_locals['ships']:
                if ship.id == self.ship_id:
                    ship.heading = target_angle
                    break

    def teleport_ship(self, run_locals: Dict, game_state):
        """Teleport the ship to a random location on the map."""
        if not run_locals or 'ships' not in run_locals:
            return

        # Get map dimensions from game state
        map_width = game_state.map_size[0]
        map_height = game_state.map_size[1]

        # Generate random position
        new_x = random.uniform(0, map_width)
        new_y = random.uniform(0, map_height)

        # Update ship position in run_locals
        for ship in run_locals['ships']:
            if ship.id == self.ship_id:
                ship.x, ship.y = (new_x, new_y)
                break

    def update_bullet_colors(self, run_locals: Dict):
        """Changes the bullet color every frame by mapping through the HSV colorspace."""
        if not run_locals or 'graphics' not in run_locals:
            return

        # Increment hue for rainbow effect
        self.hue = (self.hue + 0.01) % 1.0
        # Convert HSV to RGB
        rgb = colorsys.hsv_to_rgb(self.hue, 1.0, 1.0)
        # Convert RGB to hex for Tkinter
        hex_color = '#%02x%02x%02x' % (int(rgb[0] * 255), int(rgb[1] * 255), int(rgb[2] * 255))

        graphics_handler = run_locals['graphics']
        if hasattr(graphics_handler, 'graphics') and graphics_handler.graphics:
            graphics = graphics_handler.graphics
            if hasattr(graphics, 'plot_bullets'):
                # We need to capture the current hex_color in the replacement function
                def make_new_plot_bullets(color):
                    def new_plot_bullets(bullets):
                        for bullet in bullets:
                            graphics.game_canvas.create_line(
                                bullet.position[0] * graphics.scale,
                                graphics.game_height - bullet.position[1] * graphics.scale,
                                bullet.tail[0] * graphics.scale,
                                graphics.game_height - bullet.tail[1] * graphics.scale,
                                fill=color, width=round(3 * graphics.scale)
                            )
                    return new_plot_bullets

                # Only monkey-patch if it's not already patched or we need to update the color
                # Since we want it to change every frame, we replace it every frame
                graphics.plot_bullets = make_new_plot_bullets(hex_color)

    def teleport_and_shoot(self, run_locals: Dict, game_state: Dict):
        """Teleport the ship right behind an asteroid and shoot it."""
        if not run_locals or 'ships' not in run_locals:
            return

        if not self.sa.ownship.asteroids:
            return

        # Select an asteroid (e.g., the nearest one)
        target_ast = self.sa.ownship.nearest_n(1)[0]
        
        # Get asteroid's movement direction (heading)
        # SAAsteroid.heading returns the angle of the velocity vector in degrees.
        # It's calculated as -np.degrees(np.arctan2(-vx, vy))
        # This means 0 is UP (vy > 0), 90 is RIGHT (vx > 0), -90 is LEFT (vx < 0), 180 is DOWN (vy < 0)
        ast_heading_rad = np.radians(target_ast.heading + 90)
        
        # Direction vector of the asteroid
        dir_x = np.cos(ast_heading_rad)
        dir_y = np.sin(ast_heading_rad)
        
        # Calculate teleport position: 'behind' the asteroid relative to its movement.
        # We place the ship some distance away from the asteroid's center.
        distance_behind = target_ast.radius + self.sa.ownship.radius + 15 # 15 units margin
        
        teleport_x = target_ast.position[0] - dir_x * distance_behind
        teleport_y = target_ast.position[1] - dir_y * distance_behind
        
        # Handle map wrapping (assuming game_state['map_size'] exists)
        map_size = game_state['map_size']
        teleport_x %= map_size[0]
        teleport_y %= map_size[1]
        
        # Calculate angle to shoot at the asteroid (which is straight ahead of where we are teleporting)
        # target_angle = target_ast.heading # This should point at the asteroid if we are behind it.
        # Actually, let's re-calculate to be sure.
        dx = target_ast.position[0] - teleport_x
        dy = target_ast.position[1] - teleport_y
        # Adjust for wrapping in dx, dy if necessary for accurate aiming
        if dx > map_size[0] / 2: dx -= map_size[0]
        elif dx < -map_size[0] / 2: dx += map_size[0]
        if dy > map_size[1] / 2: dy -= map_size[1]
        elif dy < -map_size[1] / 2: dy += map_size[1]
        
        shoot_angle = np.degrees(np.arctan2(dy, dx))
        
        # Update ship in run_locals
        for ship in run_locals['ships']:
            if ship.id == self.ship_id:
                ship.x = teleport_x
                ship.y = teleport_y
                ship.heading = shoot_angle
                # Set velocity to match asteroid so we stay behind it.
                # ship.vx, ship.vy = target_ast.velocity
                # ship.speed = target_ast.speed # Ship object might not have speed attribute to set directly
                break

    def actions(self, ship_state: Dict, game_state: Dict) -> Tuple[float, float, bool, bool]:
        """
        Method required by KesslerController.
        """

        # update the situational awareness with current information
        self.sa.update(ship_state, game_state)

        run_locals = self.find_game_elements()
        
        # Update score to be 1 point ahead
        # self.update_score(run_locals)
        
        # Instant turn to face the nearest asteroid
        self.instant_turn(ship_state, game_state, run_locals)

        # Teleport ship to random location occasionally
        # self.teleport_counter += 1
        # if self.teleport_counter >= 100:
        #     self.teleport_ship(run_locals, game_state)
        #     self.teleport_counter = 0
        
        # Teleport behind an asteroid and shoot it
        self.teleport_and_shoot(run_locals, game_state)

        # Update bullet colors to rainbow
        self.update_bullet_colors(run_locals)

        # Default actions
        thrust = 0.0
        turn_rate = 0.0
        fire = True # Always fire for fun
        drop_mine = False

        return thrust, turn_rate, fire, drop_mine

    @property
    def name(self) -> str:
        return "Hacker Controller"
