import math
import gc
import inspect
import random
import colorsys
import numpy as np
from kesslergame import KesslerController, KesslerGame
from kesslergame.asteroid import Asteroid
from kesslergame.mines import Mine
from typing import Dict, Tuple, Any

from kesslergame.ship import Ship
from kesslergame.state_models import GameState

from MyAIController.sa.sa import SA


def apply_turd_mines(run_locals: Dict):
    """Overwrite the mine sprite with a turd."""
    if not run_locals or 'graphics' not in run_locals:
        return

    turd_path = "/home/scott/PycharmProjects/nafips-2026-hackathon/MyAIController/turd.png"
    gh = run_locals['graphics']
    if not hasattr(gh, 'graphics') or not gh.graphics:
        return
    g = gh.graphics

    # Only patch if it's GraphicsTK and not already patched
    if not hasattr(g, 'game_canvas') or hasattr(g, '_original_plot_mines'):
        return

    from PIL import Image, ImageTk

    # Load turd image
    try:
        # We need to know the mine radius to resize it
        # Default mine radius is 8.0 (from kesslergame/mines.py, I'll guess or try to find it)
        # Actually, let's use the mine object itself in the patched function to get the radius
        turd_img_raw = Image.open(turd_path)
        g._turd_img_raw = turd_img_raw
        g._original_plot_mines = g.plot_mines

        def patched_plot_mines(mines):
            for mine in mines:
                # Draw turd image
                mine_radius_scaled = mine.radius * g.scale
                # Check if we have a cached PhotoImage for this size
                if not hasattr(g, '_turd_sprites'):
                    g._turd_sprites = {}

                size_key = int(mine_radius_scaled * 2)
                if size_key not in g._turd_sprites:
                    resized = g._turd_img_raw.resize((size_key, size_key))
                    g._turd_sprites[size_key] = ImageTk.PhotoImage(resized)

                turd_sprite = g._turd_sprites[size_key]
                g._per_frame_images.append(turd_sprite)

                g.game_canvas.create_image(
                    mine.position[0] * g.scale,
                    g.game_height - mine.position[1] * g.scale,
                    image=turd_sprite
                )

                # Still draw detonations if they are happening
                if mine.countdown_timer < mine.detonation_time:
                    explosion_radius = mine.blast_radius * (1 - mine.countdown_timer / mine.detonation_time) ** 2
                    g.game_canvas.create_oval(
                        (mine.position[0] - explosion_radius) * g.scale,
                        g.game_height - (mine.position[1] + explosion_radius) * g.scale,
                        (mine.position[0] + explosion_radius) * g.scale,
                        g.game_height - (mine.position[1] - explosion_radius) * g.scale,
                        fill="", outline="white", width=round(10 * g.scale)
                    )

        g.plot_mines = patched_plot_mines
    except Exception as e:
        pass


def apply_patched_image(patch_image_path: str, run_locals: dict) -> str:
    if 'graphics' in run_locals:
        gh = run_locals['graphics']
        if hasattr(gh, 'graphics') and gh.graphics:
            g = gh.graphics
            # Check for GraphicsTK
            if hasattr(g, 'image_paths') and hasattr(g, 'ship_images'):
                target_path_in_list = patch_image_path

                if target_path_in_list not in g.image_paths:
                    from PIL import Image, ImageTk

                    # We need to resize it to ship_radius
                    if g.ship_images:
                        size = g.ship_images[0].size
                    else:
                        size = (35, 35)  # Fallback

                    try:
                        # Try to open the PNG first
                        new_img = Image.open(patch_image_path).resize(size)
                        # Only append to BOTH if loading succeeded
                        g.image_paths.append(target_path_in_list)
                        g.ship_images.append(new_img)
                        g.num_images = len(g.image_paths)

                        # Also update ship_sprites and ship_icons for completeness
                        if hasattr(g, 'ship_sprites'):
                            g.ship_sprites.append(ImageTk.PhotoImage(new_img))
                        if hasattr(g, 'ship_icons'):
                            g.ship_icons.append(ImageTk.PhotoImage(new_img.resize(size)))
                    except Exception as e:
                        pass
    return patch_image_path


class HackerController(KesslerController):
    def __init__(self):
        super().__init__()
        self.game_instance = None
        self.own_ship = None
        self.target_heading = None
        self.sa = SA()
        self.hue = 0.0
        self.teleport_counter = 0
        self.last_mine_frame = -100

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
        
        # If we haven't found our team ID yet, find it now from ships
        if my_team_id is None and 'ships' in run_locals:
            for ship in run_locals['ships']:
                if ship.id == self.ship_id:
                    my_team_id = ship.team
                    break

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
        """Changes the bullet color so each bullet has a unique color based on when it was shot."""
        if not run_locals or 'graphics' not in run_locals:
            return

        gh = run_locals['graphics']
        if hasattr(gh, 'graphics') and gh.graphics:
            g = gh.graphics
            if hasattr(g, 'game_canvas'):
                if not hasattr(g, '_original_plot_bullets'):
                    g._original_plot_bullets = g.plot_bullets

                # Store a reference to self (HackerController) for the closure to access its properties.
                controller = self

                def patched_plot_bullets(bullets):
                    for bullet in bullets:
                        # Use a global cache dictionary to store bullet colors
                        if not hasattr(g, '_bullet_color_cache'):
                            g._bullet_color_cache = {}

                        bullet_id = id(bullet)
                        if bullet_id not in g._bullet_color_cache:
                            # Use the current hue for this new bullet and increment the controller's hue.
                            rgb = colorsys.hsv_to_rgb(controller.hue, 1.0, 1.0)
                            g._bullet_color_cache[bullet_id] = '#%02x%02x%02x' % (int(rgb[0] * 255), int(rgb[1] * 255),
                                                                                  int(rgb[2] * 255))
                            controller.hue = (controller.hue + 0.05) % 1.0

                        g.game_canvas.create_line(
                            bullet.position[0] * g.scale,
                            g.game_height - bullet.position[1] * g.scale,
                            bullet.tail[0] * g.scale,
                            g.game_height - bullet.tail[1] * g.scale,
                            fill=g._bullet_color_cache[bullet_id], width=round(3 * g.scale)
                        )

                g.plot_bullets = patched_plot_bullets

    def teleport_and_shoot(self, run_locals: Dict, game_state: GameState):
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
        distance_behind = target_ast.radius + self.sa.ownship.radius + 45 # 15 units margin
        
        teleport_x = target_ast.position[0] - dir_x * distance_behind
        teleport_y = target_ast.position[1] - dir_y * distance_behind

        # Handle map wrapping (assuming game_state['map_size'] exists)
        map_size = game_state['map_size']
        teleport_x %= map_size[0]
        teleport_y %= map_size[1]

        # Check if the teleport position is safe (not overlapping with any asteroid)
        if not self.is_position_safe(teleport_x, teleport_y, map_size):
            # Try increasing the distance behind to find a safe spot
            for extra_dist in [20, 40, 60, 80]:
                alt_distance = distance_behind + extra_dist
                alt_x = (target_ast.position[0] - dir_x * alt_distance) % map_size[0]
                alt_y = (target_ast.position[1] - dir_y * alt_distance) % map_size[1]
                if self.is_position_safe(alt_x, alt_y, map_size):
                    teleport_x = alt_x
                    teleport_y = alt_y
                    break
            else:
                # No safe position found, skip teleport this frame
                return

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

        # Calculate base angle to asteroid
        # shoot_angle = np.degrees(np.arctan2(dy, dx))

        # Add lead angle to shoot ahead of the asteroid
        # Estimate bullet travel time based on distance and bullet speed (assumed ~2200 units/s)
        dist_to_asteroid = math.sqrt(dx * dx + dy * dy)
        bullet_speed = 2200.0  # Approximate bullet speed in kesslergame
        time_to_impact = dist_to_asteroid / bullet_speed if bullet_speed > 0 else 0

        # Calculate where asteroid will be after time_to_impact
        ast_vx, ast_vy = target_ast.velocity
        predicted_dx = dx + ast_vx * time_to_impact
        predicted_dy = dy + ast_vy * time_to_impact

        # Recalculate angle with lead
        shoot_angle = np.degrees(np.arctan2(predicted_dy, predicted_dx))

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

    def deposit_mine_ahead_of_opponent(self, run_locals: Dict, game_state: GameState):
        """Deposit a mine a little bit ahead of the opponent's current bearing."""
        if not run_locals or 'mines' not in run_locals or 'ships' not in run_locals:
            return

        if not self.sa.redships:
            return

        distance_to_opponent, opponent_ship = self.get_distance_to_opponent(game_state, run_locals)
        if distance_to_opponent < 150.0:
            return

        # Limit mine deposition frequency
        current_frame = game_state.frame
        # Only deposit a mine every 60 frames (approx once per second)
        if current_frame - self.last_mine_frame < 60:
            return
        self.last_mine_frame = current_frame

        # Get opponent heading in radians. 
        # In SAShip.update: self.heading = trim_angle(ship_dict['heading']-90)
        # So we reverse that to get the angle used by sin/cos where 0 is right.
        # Actually, let's just use np.arctan2(vy, vx) from opponent velocity if they are moving, 
        # or just use their heading. The user said "current bearing".
        
        # In kesslergame, heading 0 is UP (if I remember correctly from logic_controller.py snippet)
        # Wait, let's look at SAShip.update again:
        # self.heading = trim_angle(ship_dict['heading']-90)
        # If ship_dict['heading'] is 0 (UP), self.heading becomes -90.
        
        # Calculate position ahead of opponent.
        # In kesslergame, heading is in degrees, 0 is UP, positive is clockwise? 
        # Actually, it's usually 0 is UP, 90 is RIGHT, etc.
        # Let's use the velocity if they are moving, or heading if not.

        t_explode = 0.5
        dist_ahead = opponent_ship.speed * t_explode  # "A little bit ahead"
        heading_rad = np.radians(opponent_ship.heading)
        dx = np.sin(heading_rad) * dist_ahead
        dy = np.cos(heading_rad) * dist_ahead
        
        mine_pos = (opponent_ship.x + dx, opponent_ship.y + dy)
        
        # Wrap position
        map_size = game_state['map_size']
        mine_pos = (mine_pos[0] % map_size[0], mine_pos[1] % map_size[1])
        
        # Create and add the mine
        new_mine = Mine(mine_pos, owner=self.own_ship)
        
        # Set fuse time very low so it explodes soon? Or just leave it at 3.0.
        # User just said "deposit a mine".
        new_mine.fuse_time = t_explode
        new_mine.countdown_timer = t_explode
        
        run_locals['mines'].append(new_mine)
        
        # Update game_state if it's the real one
        if 'game_state' in run_locals:
            gs = run_locals['game_state']
            if hasattr(gs, 'add_mine'):
                gs.add_mine(new_mine.state)

    def get_distance_to_opponent(self, game_state: GameState, run_locals: dict) -> tuple[float, Ship]:
        # Get opponent ship
        opponent_ship = self.get_opponent_ship(run_locals)

        distance_to_opponent, _, _ = self.get_distance_to_ship(game_state, opponent_ship)
        return distance_to_opponent, opponent_ship

    def get_distance_to_ship(self, game_state: GameState, opponent_ship: Ship) -> tuple[float, float, float]:
        # Check if opponent is too close (within 150 units)
        dx = self.sa.ownship.position[0] - opponent_ship.x
        dy = self.sa.ownship.position[1] - opponent_ship.y

        # Handle map wrapping for distance calculation
        map_size = game_state['map_size']
        if dx > map_size[0] / 2:
            dx -= map_size[0]
        elif dx < -map_size[0] / 2:
            dx += map_size[0]
        if dy > map_size[1] / 2:
            dy -= map_size[1]
        elif dy < -map_size[1] / 2:
            dy += map_size[1]

        distance_to_opponent = math.sqrt(dx * dx + dy * dy)
        return distance_to_opponent, dx, dy

    def get_opponent_ship(self, run_locals: dict) -> Ship:
        opponent_ship: Ship = None
        for ship in run_locals['ships']:
            if ship.id != self.own_ship.id:
                opponent_ship = ship
                break
        return opponent_ship

    def is_position_safe(self, x: float, y: float, map_size: Tuple[float, float], min_clearance: float = 10.0) -> bool:
        """Check if a position is safe (not overlapping with any asteroid)."""
        for ast in self.sa.ownship.asteroids:
            dx = abs(x - ast.position[0])
            dy = abs(y - ast.position[1])

            # Handle map wrapping for distance calculation
            if dx > map_size[0] / 2:
                dx = map_size[0] - dx
            if dy > map_size[1] / 2:
                dy = map_size[1] - dy

            dist = math.sqrt(dx * dx + dy * dy)
            # Check if position is too close to asteroid (within asteroid radius + ship radius + clearance)
            if dist < (ast.radius + self.sa.ownship.radius + min_clearance):
                return False
        return True

    def tractor_beam(self, run_locals: Dict, game_state: GameState):
        """Draw a green line to the opposing ship and tweak its velocity/position."""
        target_obj = self.get_opponent_ship(run_locals)
        # Let's define a constant force F for the tractor beam
        F_magnitude = 3000000.0  # Increased force for more visible effect

        # if target_obj is None or target_obj.lives <= 0:
        if not self.sa.ownship.asteroids:
            return
        target_obj = self.get_nearest_asteroid(run_locals)
        if target_obj is None:
            return
        # Asteroids are a lot lighter, and we want to PUSH them.
        F_magnitude /= -500.0

        # F = m * a  =>  a = F / m
        dt = game_state['delta_time']
        # Use target ship's mass if available, otherwise default to 300.0
        m_target = target_obj.mass if hasattr(target_obj, 'mass') else 300.0

        dist, dx, dy = self.get_distance_to_ship(game_state, target_obj)

        if dist > 0:
            map_size = game_state['map_size']
            ux, uy = dx/dist, dy/dist
            a = F_magnitude / m_target

            # Use 1/2 a t^2 for displacement: x = x0 + v0*t + 1/2 a t^2
            # We apply the displacement directly to the target ship's position
            # Note: target_obj.vx and target_obj.vy are current velocities (v0)

            disp_x = target_obj.vx * dt + 0.5 * a * ux * (dt**2)
            disp_y = target_obj.vy * dt + 0.5 * a * uy * (dt**2)

            # Update position
            target_obj.x = (target_obj.x + disp_x) % map_size[0]
            target_obj.y = (target_obj.y + disp_y) % map_size[1]

            # Update velocity: v = v0 + a * t
            target_obj.vx += a * ux * dt
            target_obj.vy += a * uy * dt

        # Graphics: draw green line and star
        self.patch_draw_tractor_beam(run_locals, target_obj)

    def patch_draw_tractor_beam(self, run_locals: dict, target_obj):
        if 'graphics' in run_locals:
            gh = run_locals['graphics']
            if hasattr(gh, 'graphics') and gh.graphics:
                g = gh.graphics
                if hasattr(g, 'game_canvas'):
                    # Capture positions for the drawing function
                    ship_x_map = self.sa.ownship.position[0]
                    ship_y_map = self.sa.ownship.position[1]
                    ast_x_map = target_obj.x
                    ast_y_map = target_obj.y

                    # Create a persistent drawing function by monkey-patching plot_asteroids (or any other)
                    # We wrap the existing plot_asteroids to include our drawing
                    if not hasattr(g, '_original_plot_asteroids'):
                        g._original_plot_asteroids = g.plot_asteroids

                    def patched_plot_asteroids(asteroids):
                        # Call original first
                        g._original_plot_asteroids(asteroids)

                        # Now draw our tractor beam
                        ship_x = ship_x_map * g.scale
                        ship_y = g.game_height - ship_y_map * g.scale
                        ast_x = ast_x_map * g.scale
                        ast_y = g.game_height - ast_y_map * g.scale

                        g.game_canvas.create_line(ship_x, ship_y, ast_x, ast_y, fill='green', width=2, dash=(4, 4))

                        star_size = 10 * g.scale
                        for angle in [0, 45, 90, 135]:
                            rad = math.radians(angle)
                            dx_s = math.cos(rad) * star_size
                            dy_s = math.sin(rad) * star_size
                            g.game_canvas.create_line(ast_x - dx_s, ast_y - dy_s, ast_x + dx_s, ast_y + dy_s,
                                                      fill='green', width=2)

                    g.plot_asteroids = patched_plot_asteroids

    def get_nearest_asteroid(self, run_locals: dict) -> Any:
        # Get the nearest asteroid using SA
        nearest_ast = self.sa.ownship.nearest_n(2)[-1]
        # Find the corresponding asteroid object in run_locals
        target_obj = None
        for ast in run_locals['asteroids']:
            if ast.position == nearest_ast.position:
                target_obj = ast
                break
        return target_obj

    def shim_invert_opponent_controller(self, run_locals: Dict):
        """Invert the opponent's controller inputs by monkey-patching their actions method."""
        if not run_locals or 'controllers' not in run_locals:
            # We need the list of controllers, which is in the run method's frame
            # find_game_elements already extracts f_locals from KesslerGame.run
            return

        controllers = run_locals['controllers']
        for controller in controllers:
            if controller != self and not hasattr(controller, '_shimmed_invert'):
                original_actions = controller.actions

                def inverted_actions(ship_state_inner, game_state_inner, orig=original_actions):
                    thrust, turn_rate, fire, drop_mine = orig(ship_state_inner, game_state_inner)
                    # Invert the control inputs 20% of the time to be sneaky
                    if random.random() < 0.2:
                        return -thrust, -turn_rate, fire, drop_mine
                    return thrust, turn_rate, fire, drop_mine

                controller.actions = inverted_actions
                controller._shimmed_invert = True

    def apply_nyan_cat(self, run_locals: Dict):
        """Set my own ship's sprite to nyan_cat and ensure it's in the graphics handler's list."""
        if not run_locals or 'ships' not in run_locals:
            return

        nyan_path = "/home/scott/PycharmProjects/nafips-2026-hackathon/Nyan_Cat-removebg-preview.png"
        
        # Ensure nyan_cat is in the graphics handler
        nyan_path = apply_patched_image(nyan_path, run_locals)

        for ship in run_locals['ships']:
            if ship.id == self.ship_id:
                # Only apply if it's in the list to avoid IndexError
                if 'graphics' in run_locals:
                    g = run_locals['graphics'].graphics
                    if hasattr(g, 'image_paths') and nyan_path in g.image_paths:
                        ship.custom_sprite_path = nyan_path

    def apply_clown_face(self, run_locals: Dict):
        """Set the opponent's ship sprite to a clown face and ensure it's in the graphics handler's list."""
        if not run_locals or 'ships' not in run_locals:
            return

        # Use an existing PNG for now if the SVG fails, but let's try to point to a valid image
        # Actually the user asked for clown_face.svg. 
        # If PIL can't handle it, we might need to convert it or use a placeholder.
        # But let's first fix the list index issue.
        
        clown_path = "/home/scott/PycharmProjects/nafips-2026-hackathon/goofy_ahh_clown-removebg-preview.png"
        
        # Ensure clown face is in the graphics handler
        clown_path = apply_patched_image(clown_path, run_locals)

        for ship in run_locals['ships']:
            if ship.id != self.ship_id:
                # Only apply if it's in the list to avoid IndexError
                if 'graphics' in run_locals:
                    g = run_locals['graphics'].graphics
                    if hasattr(g, 'image_paths') and clown_path in g.image_paths:
                        ship.custom_sprite_path = clown_path

    def actions(self, ship_state: Dict, game_state: GameState) -> Tuple[float, float, bool, bool]:
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

        # Deposit mine ahead of opponent
        self.deposit_mine_ahead_of_opponent(run_locals, game_state)

        # Update bullet colors to rainbow
        self.update_bullet_colors(run_locals)

        # Tractor beam
        self.tractor_beam(run_locals, game_state)

        # Invert opponent controller
        self.shim_invert_opponent_controller(run_locals)

        # Apply clown face to opponent
        self.apply_clown_face(run_locals)

        # Apply nyan_cat to us
        self.apply_nyan_cat(run_locals)

        # Apply turd to mines
        apply_turd_mines(run_locals)

        # Default actions
        thrust = 0.0
        turn_rate = 0.0
        fire = True # Always fire for fun
        drop_mine = False

        return thrust, turn_rate, fire, drop_mine

    @property
    def name(self) -> str:
        return "Hacker Controller"
