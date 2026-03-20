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


class LogicController01(KesslerController):
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
        Find the asteroid most likely to hit the ship based on its bearing relative to ship heading
        and distance. Prioritizes asteroids that are close and directly in front of the ship.

        Arguments:
            game_state: GameState object containing current game state
            asteroids: Optional list of asteroids to consider. If None, uses nearest 10.

        Returns:
            Asteroid object that is most threatening, or None if no asteroids exist
        """
        if asteroids is None:
            asteroids = self.sa.ownship.nearest_n(-1)

        if not asteroids:
            return None

        best_asteroid = None
        best_threat_score = float('inf')

        # Get map dimensions for wrap-around calculations
        map_width = game_state['map_size'][0]
        map_height = game_state['map_size'][1]

        for asteroid in asteroids:
            # Calculate relative angle to asteroid
            relative_angle = trim_angle(asteroid.bearing - self.sa.ownship.heading)

            # Calculate if the asteroid is going to hit the ship
            # Compute relative velocity between asteroid and ship
            rel_vel_x = asteroid.velocity[0] - self.sa.ownship.velocity[0]
            rel_vel_y = asteroid.velocity[1] - self.sa.ownship.velocity[1]

            # Compute relative position WITH WRAP-AROUND
            dx = asteroid.position[0] - self.sa.ownship.position[0]
            dy = asteroid.position[1] - self.sa.ownship.position[1]

            # Apply wrap-around: choose shortest path
            if abs(dx) > map_width / 2:
                dx = dx - np.sign(dx) * map_width
            if abs(dy) > map_height / 2:
                dy = dy - np.sign(dy) * map_height

            rel_pos_x = dx
            rel_pos_y = dy

            # Calculate time to closest approach using relative motion
            rel_vel_mag_sq = rel_vel_x ** 2 + rel_vel_y ** 2
            if rel_vel_mag_sq > 0.001:  # Avoid division by zero
                time_to_closest = -(rel_pos_x * rel_vel_x + rel_pos_y * rel_vel_y) / rel_vel_mag_sq

                # Only consider asteroids moving toward the ship (positive time)
                if time_to_closest > 0 and time_to_closest < 10.0:  # Within 10 seconds
                    # Calculate closest approach distance
                    closest_x = rel_pos_x + rel_vel_x * time_to_closest
                    closest_y = rel_pos_y + rel_vel_y * time_to_closest
                    closest_distance = np.sqrt(closest_x ** 2 + closest_y ** 2)

                    # Consider collision threshold (ship radius + asteroid radius + safety margin)
                    collision_threshold = 50.0  # Adjust based on game parameters
                    will_hit = closest_distance < collision_threshold
                else:
                    will_hit = False
            else:
                will_hit = False

            if will_hit:
                # Threat score combines distance and angle alignment
                # Lower score means more threatening
                # Asteroids directly ahead (angle near 0) are most threatening
                angle_factor = abs(relative_angle) / 180.0  # Normalize to [0, 1]
                distance_factor = asteroid.distance / 1000.0  # Normalize distance

                # Weight angle more heavily than distance for collision threat
                # Weight smaller asteroids more to clear a path
                # Smaller asteroids get lower threat scores (higher priority)
                size_factor = asteroid.size / 4.0  # Normalize size (1-4) to [0.25, 1.0]
                threat_score = (angle_factor * 2.0) + (distance_factor * 0.5) + (size_factor * 1.5)

                if threat_score < best_threat_score:
                    best_threat_score = threat_score
                    best_asteroid = asteroid

        return best_asteroid

    def calculate_intercept_point(self, asteroid, bullet_speed=800.0):
        """
        Calculate the intercept point where we should aim to hit a moving asteroid.
        Uses iterative approach to solve the intercept problem.

        Arguments:
            asteroid: The asteroid object to intercept
            bullet_speed: Speed of the bullet (default 800.0)

        Returns:
            tuple: (intercept_x, intercept_y, time_to_intercept) or (None, None, None) if no solution
        """
        # Current positions
        ship_x, ship_y = self.sa.ownship.position
        ast_x, ast_y = asteroid.position
        ast_vx, ast_vy = asteroid.velocity

        # Initial guess: time based on current distance
        dx = ast_x - ship_x
        dy = ast_y - ship_y
        distance = np.sqrt(dx ** 2 + dy ** 2)
        time_to_intercept = distance / bullet_speed

        # Iteratively refine the intercept time (up to 5 iterations)
        for _ in range(10):
            # Predict asteroid position at intercept time
            predicted_x = ast_x + ast_vx * time_to_intercept
            predicted_y = ast_y + ast_vy * time_to_intercept

            # Calculate distance to predicted position
            dx = predicted_x - ship_x
            dy = predicted_y - ship_y
            distance = np.sqrt(dx ** 2 + dy ** 2)

            # Update time estimate
            new_time = distance / bullet_speed

            # Check for convergence
            if abs(new_time - time_to_intercept) < 0.01:
                return predicted_x, predicted_y, time_to_intercept

            time_to_intercept = new_time

        # Return the best estimate even if not fully converged
        predicted_x = ast_x + ast_vx * time_to_intercept
        predicted_y = ast_y + ast_vy * time_to_intercept
        return predicted_x, predicted_y, time_to_intercept

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
        angle_to_intercept = np.degrees(np.arctan2(dy, dx))-90.0

        # Calculate relative angle to intercept point (relative to ship heading)
        relative_angle = trim_angle(angle_to_intercept - self.sa.ownship.heading)

        for asteroid in self.sa.ownship.asteroids:
            # Get relative bearing to asteroid with wrap-around
            ast_x, ast_y = asteroid.position_wrap
            dx_ast = ast_x - ship_x
            dy_ast = ast_y - ship_y
            angle_to_asteroid = np.degrees(np.arctan2(dy_ast, dx_ast)) - 90.0
            rel_angle_to_ast = trim_angle(angle_to_asteroid - self.sa.ownship.heading)
            
            # If the asteroid is within its angular width from our heading, we are "aimed" at it.
            # Angular width = arctan(radius / distance)
            ast_dist = asteroid.distance_wrap
            if ast_dist > 0:
                angular_width = np.degrees(np.arctan2(asteroid.radius, ast_dist))
                if abs(rel_angle_to_ast) < angular_width:
                    fire = True
                    break

        drop_mine = False

        # this converts the desired aiming angle to a control action to be fed to the ship in terms of turn rate
        # set turn rate to 0
        turn_rate = np.sign(relative_angle)*np.clip(abs(3*relative_angle), 90.0, 180.0)
        if abs(relative_angle) < 0.5:
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

        # Back away from the nearest asteroid
        # Find the actual nearest asteroid (not necessarily the most threatening)
        true_nearest_asteroid = self.sa.ownship.nearest_n(1)[0]
        
        # Calculate bearing to nearest asteroid relative to ship heading
        # Note: self.sa.ownship.heading is already trimmed
        asteroid_bearing = true_nearest_asteroid.bearing
        relative_asteroid_bearing = trim_angle(asteroid_bearing - self.sa.ownship.heading)
        
        # Decision: drive forward or backward based upon the optimal escape trajectory.
        # If asteroid is in front (+/- 90 deg), drive backward.
        # If asteroid is behind, drive forward.
        distance_to_asteroid = true_nearest_asteroid.distance
        # Scale thrust based on distance - only move if asteroid is reasonably close
        distance_threshold = 150.0  # Only react if asteroid is within this distance

        if distance_to_asteroid < distance_threshold:
            # Scale thrust proportionally: closer asteroids get stronger thrust
            thrust_scale = 1.0 - (distance_to_asteroid / distance_threshold)

            if abs(relative_asteroid_bearing) < 90:
                thrust = -ship_state["thrust_range"][1] * thrust_scale  # Back away, scaled by distance
            else:
                thrust = ship_state["thrust_range"][1] * thrust_scale  # Drive forward, scaled by distance
        else:
            thrust = 0.0  # Don't move if asteroid is far away

        fire = fire or bool(abs(relative_angle) < 15.0)
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
