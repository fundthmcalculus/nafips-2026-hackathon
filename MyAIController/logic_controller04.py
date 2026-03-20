# -*- coding: utf-8 -*-
# Copyright © 2022 Thales. All Rights Reserved.
# NOTICE: This file is subject to the license agreement defined in file 'LICENSE', which is part of
# this source code package.

from typing import Dict, Tuple

import numpy as np
from kesslergame import KesslerController
from kesslergame.state_models import GameState

# from MyAIController.ai.sa.sa import SA
from .sa.sa import SA
from .sa.util.helpers import trim_angle


class LogicController04(KesslerController):
    def __init__(self):
        """
        Any variables or initialization desired for the controller can be set up here
        """
        self.normalization_dist = None
        self.sa = SA()

        self.shot_asteroids = set()
        self.last_shot_clear_time = 60
        self.clear_frames = 60

    def get_most_threatening_asteroid(self, game_state: GameState, asteroids=None):
        """
        Find the asteroid most likely to hit the ship or one that is easily targetable.
        """
        if asteroids is None:
            asteroids = self.sa.ownship.asteroids

        if not asteroids:
            return None

        best_asteroid = None
        best_threat_score = float('inf')

        ship_x, ship_y = self.sa.ownship.position
        ship_vx, ship_vy = self.sa.ownship.velocity
        ship_heading = self.sa.ownship.heading
        ship_radius = self.sa.ownship.radius
        map_width, map_height = game_state['map_size']

        for asteroid in asteroids:
            # Position relative to ship with wrap-around
            ast_x, ast_y = asteroid.position_wrap
            dx = ast_x - ship_x
            dy = ast_y - ship_y
            
            # Distance
            dist = asteroid.distance_wrap
            
            # Relative velocity
            rel_vx = asteroid.velocity[0] - ship_vx
            rel_vy = asteroid.velocity[1] - ship_vy
            
            # Time to closest approach
            rel_vel_sq = rel_vx**2 + rel_vy**2
            if rel_vel_sq > 0.1:
                t_ca = -(dx * rel_vx + dy * rel_vy) / rel_vel_sq
            else:
                t_ca = -1
            
            collision_imminent = False
            if 0 < t_ca < 5.0:
                # Closest approach distance
                ca_dx = dx + rel_vx * t_ca
                ca_dy = dy + rel_vy * t_ca
                ca_dist = np.sqrt(ca_dx**2 + ca_dy**2)
                
                if ca_dist < (ship_radius + asteroid.radius + 30.0):
                    collision_imminent = True

            # Calculate bearing and relative angle
            angle_to_ast = asteroid.bearing_wrap
            rel_angle = abs(trim_angle(angle_to_ast - ship_heading))
            
            # Threat score calculation
            if collision_imminent:
                # High priority for imminent collisions
                threat_score = t_ca * 2.0 + dist * 0.05 + rel_angle * 0.05
            else:
                # Normal priority based on distance and angle
                # Favor those directly in front to hit more
                # Slightly more weight on distance for survival and clearing immediate area
                threat_score = 100.0 + dist * 0.5 + rel_angle * 0.6 + (asteroid.size * 2.0)
            
            # Extra bonus for being currently aimed at - rapid snapping
            if rel_angle < 30.0:
                threat_score -= 50.0

            if threat_score < best_threat_score:
                best_threat_score = threat_score
                best_asteroid = asteroid

        return best_asteroid

    def calculate_intercept_point(self, asteroid, bullet_speed=800.0):
        """
        Calculate the intercept point where we should aim to hit a moving asteroid.
        Uses iterative approach to solve the intercept problem.
        """
        # Current positions
        ship_x, ship_y = self.sa.ownship.position
        ship_vx, ship_vy = self.sa.ownship.velocity
        
        # Asteroid position with wrap-around relative to ship
        ast_x, ast_y = asteroid.position_wrap
        ast_vx, ast_vy = asteroid.velocity

        # Relative velocity (bullet velocity will be relative to ship's velocity at time of firing)
        # In kesslergame, bullet velocity = ship_velocity + bullet_speed * [cos(heading), sin(heading)]
        # So we want to solve: Ship_Pos + Ship_Vel * t + Bullet_Vel_Rel * t = Ast_Pos + Ast_Vel * t
        # (Ship_Pos - Ast_Pos) + (Ship_Vel - Ast_Vel) * t + Bullet_Vel_Rel * t = 0
        # Let dP = Ast_Pos - Ship_Pos, dV = Ast_Vel - Ship_Vel
        # Bullet_Vel_Rel * t = dP + dV * t
        # |Bullet_Vel_Rel|^2 * t^2 = |dP + dV * t|^2
        # bullet_speed^2 * t^2 = |dP|^2 + 2(dP . dV) * t + |dV|^2 * t^2
        # (bullet_speed^2 - |dV|^2) * t^2 - 2(dP . dV) * t - |dP|^2 = 0
        
        dx = ast_x - ship_x
        dy = ast_y - ship_y
        dvx = ast_vx - ship_vx
        dvy = ast_vy - ship_vy
        
        a = bullet_speed**2 - (dvx**2 + dvy**2)
        b = -2 * (dx * dvx + dy * dvy)
        c = -(dx**2 + dy**2)
        
        discriminant = b**2 - 4*a*c
        if discriminant < 0:
            return ast_x, ast_y, 0.0 # Should not happen with high bullet speed
        
        t1 = (-b + np.sqrt(discriminant)) / (2*a)
        t2 = (-b - np.sqrt(discriminant)) / (2*a)
        
        t = max(t1, t2)
        if t < 0:
            t = 0
            
        predicted_x = ast_x + ast_vx * t
        predicted_y = ast_y + ast_vy * t
        
        return predicted_x, predicted_y, t

    def find_escape_target(self, game_state: GameState):
        """
        Find the nearest empty region reachable within 3 seconds.
        """
        ship_x, ship_y = self.sa.ownship.position
        map_width, map_height = game_state['map_size']
        
        # Max reachable distance in 3 seconds
        # Using a conservative estimate: 
        # max_accel = 480 m/s^2, time = 3s. dist = 0.5 * 480 * 3^2 = 2160 m (large!)
        # But we are also limited by max speed (240 m/s). dist = 240 * 3 = 720 m.
        # Let's search within 500-700m radius.
        search_radius = 500.0
        
        # Sample points around the ship
        num_samples = 16
        candidate_points = []
        for i in range(num_samples):
            angle = 2 * np.pi * i / num_samples
            # Sample at different distances
            for r in [search_radius * 0.5, search_radius]:
                px = (ship_x + r * np.cos(angle)) % map_width
                py = (ship_y + r * np.sin(angle)) % map_height
                candidate_points.append((px, py))
        
        best_point = None
        max_min_dist = -1.0
        
        # Predicted asteroid positions in 3 seconds
        predicted_asteroids = []
        for asteroid in self.sa.ownship.asteroids:
            ax, ay = asteroid.position
            avx, avy = asteroid.velocity
            # Predict position with wrap-around
            p_ax = (ax + avx * 3.0) % map_width
            p_ay = (ay + avy * 3.0) % map_height
            predicted_asteroids.append((p_ax, p_ay, asteroid.radius))
            
        for px, py in candidate_points:
            min_dist_to_asteroid = float('inf')
            for ax, ay, radius in predicted_asteroids:
                dx = px - ax
                dy = py - ay
                # Wrap-around distance
                if abs(dx) > map_width / 2:
                    dx = dx - np.sign(dx) * map_width
                if abs(dy) > map_height / 2:
                    dy = dy - np.sign(dy) * map_height
                
                dist = np.sqrt(dx**2 + dy**2) - radius
                if dist < min_dist_to_asteroid:
                    min_dist_to_asteroid = dist
            
            if min_dist_to_asteroid > max_min_dist:
                max_min_dist = min_dist_to_asteroid
                best_point = (px, py)
        
        return best_point

    def actions(self, ship_state: Dict, game_state: GameState) -> Tuple[float, float, bool, bool]:
        """
        Method processed each time step by this controller to determine what control actions to take

        Arguments:
            ship_state (ShipState): contains state information for your own ship
            game_state (GameState): contains state information for all objects in the game

        Returns:
            float: thrust control value
            float: turn-rate control value
            bool: fire control value. Shoots if true
            bool: mine deployment control value. Lays mine if true
        """
        
        # update the situational awareness with current information
        self.sa.update(ship_state, game_state)

        # Clear shot asteroids periodically
        if game_state.time - self.last_shot_clear_time > 0.5:
            self.shot_asteroids.clear()
            self.last_shot_clear_time = game_state.time

        # Mine laying strategy
        # 1) If I am near another ship
        # 2) If there are a lot of asteroids close by
        drop_mine = False
        
        # Check if near another ship
        near_ship = False
        ship_x, ship_y = self.sa.ownship.position
        map_width, map_height = game_state['map_size']
        for red_ship in self.sa.redships:
            red_x, red_y = red_ship.position
            dx = red_x - ship_x
            dy = red_y - ship_y
            if abs(dx) > map_width / 2:
                dx = dx - np.sign(dx) * map_width
            if abs(dy) > map_height / 2:
                dy = dy - np.sign(dy) * map_height
            dist_to_red = np.sqrt(dx**2 + dy**2)
            if dist_to_red < 30.0:  # Threshold for "near"
                near_ship = True
                break
        
        # Check if a lot of asteroids are close by
        asteroids_nearby = self.sa.ownship.within_radius_wrap(100.0)
        many_asteroids = len(asteroids_nearby) >= 5
        
        # We'll use the local drop_mine variable calculated here
        should_drop_mine = near_ship or many_asteroids

        # Ramming strategy: if I am very close to the enemy ship, and he has fewer lives than me, ram him.
        for red_ship in self.sa.redships:
            red_x, red_y = red_ship.position
            dx = red_x - ship_x
            dy = red_y - ship_y
            if abs(dx) > map_width / 2:
                dx = dx - np.sign(dx) * map_width
            if abs(dy) > map_height / 2:
                dy = dy - np.sign(dy) * map_height
            dist_to_red = np.sqrt(dx**2 + dy**2)
            
            if dist_to_red < 200.0 and red_ship.lives < self.sa.ownship.lives:
                # Ramming mode!
                angle_to_red = np.degrees(np.arctan2(dy, dx)) - 90.0
                rel_angle_to_red = trim_angle(angle_to_red - self.sa.ownship.heading)
                
                turn_rate = np.sign(rel_angle_to_red) * np.clip(abs(3 * rel_angle_to_red), 90.0, 180.0)
                if abs(rel_angle_to_red) < 0.5:
                    turn_rate = 0.0
                
                if abs(rel_angle_to_red) < 30:
                    thrust = ship_state.thrust_range[1]
                else:
                    thrust = 0.0
                
                fire = True # Also shoot while ramming
                return thrust, turn_rate, fire, should_drop_mine

        fire = False

        # get the asteroid that is most likely to hit the ship
        nearest_asteroid = self.get_most_threatening_asteroid(game_state)

        if nearest_asteroid is None:
            # If everything has been shot, just take the one closest to our current heading
            if self.sa.ownship.asteroids:
                nearest_asteroid = min(self.sa.ownship.asteroids,
                                       key=lambda a: abs(trim_angle(a.bearing - self.sa.ownship.heading)))
            else:
                nearest_asteroid = None

        if nearest_asteroid is None:
            return 0.0, 0.0, False, False

        # Calculate intercept point considering asteroid velocity and bullet travel time
        intercept_x, intercept_y, time_to_intercept = self.calculate_intercept_point(nearest_asteroid)

        # Calculate angle to intercept point
        ship_x, ship_y = self.sa.ownship.position
        dx = intercept_x - ship_x
        dy = intercept_y - ship_y
        
        angle_to_intercept = np.degrees(np.arctan2(-dx, dy)) # Consistent with saasteroids bearing

        # Calculate relative angle to intercept point (relative to ship heading)
        relative_angle = trim_angle(angle_to_intercept - self.sa.ownship.heading)

        for asteroid in self.sa.ownship.asteroids:
            # Get relative bearing to asteroid with wrap-around
            rel_angle_to_ast = trim_angle(asteroid.bearing_wrap - self.sa.ownship.heading)
            
            # If the asteroid is within its angular width from our heading, we are "aimed" at it.
            ast_dist = asteroid.distance_wrap
            if ast_dist > 0:
                angular_width = np.degrees(np.arctan2(asteroid.radius + 2.0, ast_dist))
                # Very generous cone to maximize hit rate while turning
                if abs(rel_angle_to_ast) < max(angular_width, 25.0):
                    fire = True
                    break

        drop_mine = False

        # Scale turn rate for more aggressive aiming
        # Use high gain and a floor to snap between targets
        turn_rate = np.sign(relative_angle) * np.clip(abs(20 * relative_angle), 90.0, 180.0)
        
        if abs(relative_angle) < 0.05:
            turn_rate = 0.0

        # Emergency escape logic when invincible and too close to an asteroid
        is_invincible = ship_state.is_respawning
        too_close = False
        ship_radius = self.sa.ownship.radius
        
        # Check all asteroids to see if any are "too close" or "on top of"
        for asteroid in self.sa.ownship.asteroids:
            # Distance wrap is preferred for accuracy near map edges
            if asteroid.distance_wrap < (ship_radius + asteroid.radius + 10.0): # 10.0 safety margin
                too_close = True
                break
        
        if is_invincible and too_close:
            # DON'T SHOOT
            fire = False
            
            # Accelerate away towards the nearest empty region reachable within 3 seconds
            escape_target = self.find_escape_target(game_state)
            if escape_target:
                target_x, target_y = escape_target
                ship_x, ship_y = self.sa.ownship.position
                
                # Calculate angle to target with wrap-around
                map_width, map_height = game_state.map_size
                dx = target_x - ship_x
                dy = target_y - ship_y
                if abs(dx) > map_width / 2:
                    dx = dx - np.sign(dx) * map_width
                if abs(dy) > map_height / 2:
                    dy = dy - np.sign(dy) * map_height
                
                angle_to_target = np.degrees(np.arctan2(dy, dx)) - 90.0
                rel_angle_to_target = trim_angle(angle_to_target - self.sa.ownship.heading)
                
                # Aim at target
                turn_rate = np.sign(rel_angle_to_target) * np.clip(abs(3 * rel_angle_to_target), 90.0, 180.0)
                if abs(rel_angle_to_target) < 0.5:
                    turn_rate = 0.0
                
                # Full thrust if aiming reasonably well, otherwise just turn
                if abs(rel_angle_to_target) < 30:
                    thrust = ship_state.thrust_range[1]
                else:
                    thrust = 0.0
                
                # Skip normal asteroid-based movement/shooting
                if nearest_asteroid:
                    self.shot_asteroids.discard(id(nearest_asteroid)) # Don't mark as shot if we didn't fire
                    
                return thrust, turn_rate, fire, should_drop_mine

        # Scale thrust based on distance to nearest asteroid
        true_nearest_asteroid = self.sa.ownship.nearest_n_wrap(1)[0]
        asteroid_bearing = true_nearest_asteroid.bearing_wrap
        relative_asteroid_bearing = trim_angle(asteroid_bearing - self.sa.ownship.heading)
        distance_to_asteroid = true_nearest_asteroid.distance_wrap
        
        # Safe distance we want to keep
        safe_distance = 150.0
        
        if distance_to_asteroid < safe_distance:
            # We are too close.
            # If the asteroid is in front (+/- 90 deg), back away.
            # If it's behind, drive forward.
            thrust_scale = 1.0 - (distance_to_asteroid / safe_distance)
            if abs(relative_asteroid_bearing) < 90:
                thrust = -ship_state["thrust_range"][1] * thrust_scale
            else:
                thrust = ship_state["thrust_range"][1] * thrust_scale
        else:
            # If we are at a safe distance, check if we are moving towards something dangerous
            ship_speed = self.sa.ownship.speed
            
            # Reduce max speed to have more time to react and turn
            if ship_speed > 40:
                thrust = -ship_state["thrust_range"][1] * 0.4
            else:
                thrust = 0.0

        # Override fire if we are pointing almost at our target
        fire = fire or bool(abs(relative_angle) < 5.0)
        drop_mine = should_drop_mine

        if fire and nearest_asteroid:
            self.shot_asteroids.add(id(nearest_asteroid))

        return thrust, turn_rate, fire, drop_mine

    @property
    def name(self) -> str:
        """
        Simple property used for naming controllers such that it can be displayed in the graphics engine

        Returns:
            str: name of this controller
        """
        return type(self).__name__

    # @property
    # def custom_sprite_path(self) -> str:
    #     return "Neo.png"
