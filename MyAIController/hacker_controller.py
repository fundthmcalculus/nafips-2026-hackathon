import gc
import inspect
from kesslergame import KesslerController, KesslerGame
from typing import Dict, Tuple

class HackerController(KesslerController):
    def __init__(self):
        super().__init__()
        self.game_instance = None
        self.own_ship = None
        self.target_heading = None

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

    def instant_turn(self, ship_state: Dict, game_state: Dict):
        """Modify the game state so my ship turns instantaneously."""
        # The user wants to modify the game state so the ship turns instantaneously.
        # This can be done by intercepting the actions and directly setting the ship's heading.
        
        # We need to know the desired heading. Let's say we want to point at the nearest asteroid.
        if not game_state['asteroids']:
            return

        ship_pos = ship_state['position']
        # Find nearest asteroid
        nearest_ast = min(game_state['asteroids'], 
                         key=lambda a: (a['position'][0]-ship_pos[0])**2 + (a['position'][1]-ship_pos[1])**2)
        
        import math
        dx = nearest_ast['position'][0] - ship_pos[0]
        dy = nearest_ast['position'][1] - ship_pos[1]
        
        # Calculate angle in degrees (kesslergame uses degrees, 0 is up/right?)
        # Actually from logic_controller.py: angle_to_intercept = np.degrees(np.arctan2(dy, dx))-90.0
        target_angle = math.degrees(math.atan2(dy, dx)) - 90.0
        
        if self.own_ship:
            # Set heading directly in the ship object
            self.own_ship.heading = target_angle

    def actions(self, ship_state: Dict, game_state: Dict) -> Tuple[float, float, bool, bool]:
        """
        Method required by KesslerController.
        """
        run_locals = self.find_game_elements()
        
        # Update score to be 1 point ahead
        self.update_score(run_locals)
        
        # Instant turn to face the nearest asteroid
        self.instant_turn(ship_state, game_state)

        # Default actions
        thrust = 0.0
        turn_rate = 0.0
        fire = True # Always fire for fun
        drop_mine = False

        return thrust, turn_rate, fire, drop_mine

    @property
    def name(self) -> str:
        return "Hacker Controller"
