

from datetime import datetime, timedelta
import threading

class Bids:
    def __init__(self, player_id, bid,wage, bidding_team, teams_df, players_df, typeo):
        self.player_id = player_id
        self.bidding_team = bidding_team
        self.outgoing_team = self.find_outgoing_team(players_df)
        self.bid = bid
        self.wage = wage
        self.starting_time = datetime.now()
        self.ending_time = self.starting_time + timedelta(hours=12)
        self.active = True
        self.players_df = players_df
        self.teams_df = teams_df
        self.player_name_row = self.players_df[self.players_df['player_id'] == self.player_id]
        self.player_name = self.player_name_row['name'].iloc[
            0] if not self.player_name_row.empty else f"ID {self.player_id} (Name Unknown)"
        self.typeo = typeo
        # Schedule auto-expiration
        self._timer = threading.Timer(60, self.expire_bid) #12 hours is 12*3600
        self._timer.daemon = True
        self._timer.start()




    def find_outgoing_team(self, players_df):
        """Get current team for the player from the players DataFrame."""
        row = players_df.loc[players_df["player_id"] == self.player_id]
        if not row.empty:
            return row.iloc[0]["club_id"]
        return None

    def calculate_wage(self): #placeholder
        return self.bid * 0.05

    def expire_bid(self):
        self.active = False
        print(f"Bid for player {self.player_id} expired at {datetime.now()}.")

    def is_active(self):
        return self.active and datetime.now() < self.ending_time

    def time_remaining(self):
        remaining = self.ending_time - datetime.now()
        print(f"remaining: {remaining}")
        return remaining if remaining.total_seconds() > 0 else timedelta(0)

    def __repr__(self):
        status = "Active" if self.is_active() else "Expired"
        return f"<Bid player={self.player_id}, team={self.bidding_team}, {status}>"

    def deactivate_bid(self):
        if self.active:
            self.active = False
            self._timer.cancel()
            print(f"Bid for player {self.player_id} manually deactivated at {datetime.now()}.")
            return True
        else:
            print(f"Bid for player {self.player_id} is already inactive/expired.")
            return False