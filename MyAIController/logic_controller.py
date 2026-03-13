# -*- coding: utf-8 -*-
# Copyright © 2022 Thales. All Rights Reserved.
# NOTICE: This file is subject to the license agreement defined in file 'LICENSE', which is part of
# this source code package.

from kesslergame import KesslerController
from typing import Dict, Tuple
# from MyAIController.ai.sa.sa import SA
from .sa.sa import SA
from .sa.util.helpers import trim_angle
import skfuzzy.control as ctrl
import skfuzzy as skf
import numpy as np


class LogicController(KesslerController):
    def __init__(self, chromosome=None):
        """
        Any variables or initialization desired for the controller can be set up here
        """
        self.chromosome = chromosome
        self.aiming_fis = None
        self.aiming_fis_sim = None
        self.normalization_dist = None
        self.sa = SA()

        self.shot_asteroids = set()
        self.last_shot_clear_time = 60
        self.clear_frames = 60

        # I put this in a separate function for cleanliness in the init procedure, but this just calls the functions
        # that create your FIS functions
        self.create_fuzzy_systems()

    def create_aiming_fis(self):
        # If we don't have a chromosome to get values from, use "default" values
        if not self.chromosome:
            # input 1 - distance to asteroid
            distance = ctrl.Antecedent(np.linspace(0.0, 1.0, 11), "distance")
            # input 2 - angle to asteroid (relative to ship heading)
            angle = ctrl.Antecedent(np.linspace(-1.0, 1.0, 11), "angle")

            # output - desired relative angle to match to aim ship at asteroid
            aiming_angle = ctrl.Consequent(np.linspace(-1.0, 1.0, 11), "aiming_angle")

            # creating 3 equally spaced membership functions for the inputs
            distance.automf(3, names=["close", "medium", "far"])
            angle.automf(3, names=["negative", "zero", "positive"])

            # creating 3 triangular membership functions for the output
            aiming_angle["negative"] = skf.trimf(aiming_angle.universe, [-1.0, -1.0, 0.0])
            aiming_angle["zero"] = skf.trimf(aiming_angle.universe, [-1.0, 0.0, 1.0])
            aiming_angle["positive"] = skf.trimf(aiming_angle.universe, [0.0, 1.0, 1.0])

            # creating the rule base for the fuzzy system
            rule1 = ctrl.Rule(distance["close"] & angle["negative"], aiming_angle["negative"])
            rule2 = ctrl.Rule(distance["medium"] & angle["negative"], aiming_angle["negative"])
            rule3 = ctrl.Rule(distance["far"] & angle["negative"], aiming_angle["negative"])
            rule4 = ctrl.Rule(distance["close"] & angle["zero"], aiming_angle["negative"])
            rule5 = ctrl.Rule(distance["medium"] & angle["zero"], aiming_angle["positive"])
            rule6 = ctrl.Rule(distance["far"] & angle["zero"], aiming_angle["positive"])
            rule7 = ctrl.Rule(distance["close"] & angle["positive"], aiming_angle["positive"])
            rule8 = ctrl.Rule(distance["medium"] & angle["positive"], aiming_angle["positive"])
            rule9 = ctrl.Rule(distance["far"] & angle["positive"], aiming_angle["positive"])

            rules = [rule1, rule2, rule3, rule4, rule5, rule6, rule7, rule8, rule9]
            # creating a FIS controller from the rules + membership functions
            self.aiming_fis = ctrl.ControlSystem(rules)
            # creating a controller sim to evaluate the FIS
            self.aiming_fis_sim = ctrl.ControlSystemSimulation(self.aiming_fis)
        else:
            # create FIS using GA chromosome
            # input 1 - distance to asteroid
            distance = ctrl.Antecedent(np.linspace(0.0, 1.0, 11), "distance")
            # input 2 - angle to asteroid (relative to ship heading)
            angle = ctrl.Antecedent(np.linspace(-1.0, 1.0, 11), "angle")

            # output - desired relative angle to match to aim ship at asteroid
            aiming_angle = ctrl.Consequent(np.linspace(-1.0, 1.0, 11), "aiming_angle")

            # Create membership functions from chromosome - Note that we're constraining the triangular membership
            # functions to have Ruspini partitioning
            # create distance membership functions from chromosome
            distance["close"] = skf.trimf(distance.universe, [-1.0, -1.0, self.chromosome[0]])
            distance["medium"] = skf.trimf(distance.universe, [-1.0, self.chromosome[0], 1.0])
            distance["far"] = skf.trimf(distance.universe, [self.chromosome[0], 1.0, 1.0])
            # create angle membership functions from chromosome
            angle["negative"] = skf.trimf(angle.universe, [-1.0, -1.0, self.chromosome[1]*2-1])
            angle["zero"] = skf.trimf(angle.universe, [-1.0, self.chromosome[1]*2-1, 1.0])
            angle["positive"] = skf.trimf(angle.universe, [self.chromosome[1]*2-1, 1.0, 1.0])

            # creating 3 triangular membership functions for the output
            aiming_angle["negative"] = skf.trimf(aiming_angle.universe, [-1.0, -1.0, self.chromosome[2]*2-1])
            aiming_angle["zero"] = skf.trimf(aiming_angle.universe, [-1.0, self.chromosome[2]*2-1, 1.0])
            aiming_angle["positive"] = skf.trimf(aiming_angle.universe, [self.chromosome[2]*2-1, 1.0, 1.0])

            input1_mfs = [distance["close"], distance["medium"], distance["far"]]
            input2_mfs = [angle["negative"], angle["zero"], angle["positive"]]

            # create list of output membership functions to index into to create rule antecedents
            output_mfs = [aiming_angle["negative"], aiming_angle["zero"], aiming_angle["positive"]]

            # bin the values associated with rules - this is done so we can use the floats in the chromosome DNA
            # associated with the output membership functions in order to index into our predefined output membership
            # function set - i.e. the "output_mfs" list
            bins = np.array([0.0, 0.33333, 0.66666, 1.0])
            num_mfs1 = len(input1_mfs)
            num_mfs2 = len(input2_mfs)
            num_rules = num_mfs1*num_mfs2
            # grabbing the corresponding DNA values that determine the output mfs from the chromosome
            rules_raw = self.chromosome[3:3+num_rules]
            # binning the values to convert the floats to integer values to be used as indices - a somewhat hacky way
            # using direct integer encodings would be nicer and probably perform better - opportunity for improvement
            ind = np.digitize(rules_raw, bins, right=True)-1
            ind = [int(min(max(idx, 0), 2)) for idx in ind]


            count = 0
            # mapping the DNA indices to output_mfs
            try:
                rule_consequents_linear = [output_mfs[idx] for idx in ind]
            except:
                print(ind)
                print(rules_raw)
            # constructing the rules by combining our antecedents (conjunction of input mfs) with the corresponding
            # consequents (output mfs)
            rules = []

            for jj in range(num_mfs2):
                for ii in range(num_mfs1):
                    rules.append(ctrl.Rule(input1_mfs[ii] & input2_mfs[jj], rule_consequents_linear[count]))

            # creating a FIS controller from the rules + membership functions
            self.aiming_fis = ctrl.ControlSystem(rules)
            # creating a controller sim to evaluate the FIS
            self.aiming_fis_sim = ctrl.ControlSystemSimulation(self.aiming_fis)

    def create_fuzzy_systems(self):
        self.create_aiming_fis()

    def get_most_threatening_asteroid(self, asteroids=None):
        """
        Find the asteroid most likely to hit the ship based on its bearing relative to ship heading
        and distance. Prioritizes asteroids that are close and directly in front of the ship.

        Arguments:
            asteroids: Optional list of asteroids to consider. If None, uses nearest 10.

        Returns:
            Asteroid object that is most threatening, or None if no asteroids exist
        """
        if asteroids is None:
            asteroids = self.sa.ownship.nearest_n(10)

        if not asteroids:
            return None

        best_asteroid = None
        best_threat_score = float('inf')

        for asteroid in asteroids:
            # Calculate relative angle to asteroid
            relative_angle = trim_angle(asteroid.bearing - self.sa.ownship.heading)

            # Calculate if the asteroid is going to hit the ship
            # Compute relative velocity between asteroid and ship
            rel_vel_x = asteroid.velocity[0] - self.sa.ownship.velocity[0]
            rel_vel_y = asteroid.velocity[1] - self.sa.ownship.velocity[1]

            # Compute relative position
            rel_pos_x = asteroid.position[0] - self.sa.ownship.position[0]
            rel_pos_y = asteroid.position[1] - self.sa.ownship.position[1]

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
                threat_score = (angle_factor * 2.0) + (distance_factor * 0.5)

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
        for _ in range(5):
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

    def actions(self, ship_state: Dict, game_state: Dict) -> Tuple[float, float, bool, bool]:
        """
        Method processed each time step by this controller to determine what control actions to take

        Arguments:
            ship_state (dict): contains state information for your own ship
            game_state (dict): contains state information for all objects in the game

        Returns:
            float: thrust control value
            float: turn-rate control value
            bool: fire control value. Shoots if true
            bool: mine deployment control value. Lays mine if true
        """
        
        # update the situational awareness with current information
        self.sa.update(ship_state, game_state)


        # Every 2 seconds, clear out shot asteroids in case we missed
        if self.last_shot_clear_time > self.clear_frames:
            self.shot_asteroids.clear()
            self.last_shot_clear_time = 0
        self.last_shot_clear_time += 1

        # Filter out asteroids that have already been shot
        current_asteroid_ids = {id(ast) for ast in self.sa.ownship.asteroids}
        self.shot_asteroids = {ast_id for ast_id in self.shot_asteroids if ast_id in current_asteroid_ids}
        
        available_asteroids = [ast for ast in self.sa.ownship.asteroids if id(ast) not in self.shot_asteroids]

        # get the asteroid that is most likely to hit the ship
        nearest_asteroid = self.get_most_threatening_asteroid(available_asteroids[:10] if available_asteroids else None)

        if nearest_asteroid is None:
            # No threatening asteroids, default to nearest available
            if available_asteroids:
                # Sort by distance manually since we filtered the list
                available_asteroids.sort(key=lambda x: x.distance)
                nearest_asteroid = available_asteroids[0]
            else:
                # If everything has been shot, just take the nearest one regardless
                nearest_asteroid = self.sa.ownship.nearest_n(1)[0] if self.sa.ownship.asteroids else None

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
        norm_relative_angle = self.sa.norm_angle(relative_angle)

        # Use distance to intercept point for fuzzy input
        distance = np.sqrt(dx ** 2 + dy ** 2)
        norm_ast_distance = self.sa.norm_distance(distance)

        # feed asteroid dist and angle to the FIS
        self.aiming_fis_sim.input["angle"] = norm_relative_angle
        self.aiming_fis_sim.input["distance"] = norm_ast_distance
        # compute fis output
        self.aiming_fis_sim.compute()
        # map normalized output to angle range [-180, 180], note that the output of the fis is determined by the membership functions and they go from -1 to 1
        desired_aim_angle = self.aiming_fis_sim.output["aiming_angle"]*180.0
        aim_angle_difference = relative_angle  # trim_angle(desired_aim_angle - relative_angle)

        # this converts the desired aiming angle to a control action to be fed to the ship in terms of turn rate
        # set turn rate to 0
        turn_rate = np.sign(relative_angle)*np.clip(abs(3*relative_angle), 45.0, 180.0)
        if abs(relative_angle) < 0.5:
            turn_rate = 0.0

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
        distance_threshold = 300.0  # Only react if asteroid is within this distance

        if distance_to_asteroid < distance_threshold:
            # Scale thrust proportionally: closer asteroids get stronger thrust
            thrust_scale = 1.0 - (distance_to_asteroid / distance_threshold)

            if abs(relative_asteroid_bearing) < 90:
                thrust = -ship_state["thrust_range"][1] * thrust_scale  # Back away, scaled by distance
            else:
                thrust = ship_state["thrust_range"][1] * thrust_scale  # Drive forward, scaled by distance
        else:
            thrust = 0.0  # Don't move if asteroid is far away

        fire = bool(abs(relative_angle) < 45.0)
        drop_mine = False

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
        return "Fuzzy Test1"

    # @property
    # def custom_sprite_path(self) -> str:
    #     return "Neo.png"
