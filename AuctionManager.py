import os

import pandas as pd
from datetime import datetime
from Bids import Bids



class AuctionManager:
    def __init__(self, team_df, players_df):
        # Load data once here
        self.teams_df = team_df
        self.players_df = players_df
        self.bids = []  # store all bids here
        print(f"AuctionManager initialized at {datetime.now()}")
    def can_bid_be_placed(self,player_id, bid_amount, bidding_team, wage):

        #check if player can be bided on
        player_row = self.players_df.loc[self.players_df["player_id"] == player_id]
        if player_row.empty:
            return False, f"Player {player_id} not found."
        player = player_row.iloc[0]
        if not (player["is_listed"] or player["club_name"] == "rotw"):
            for b in self.bids:
                if b.player_id == player_id:
                    if not b.is_active:
                        return False, f"Player {player_id} not listed."
        if player["Type"] != "Regular":
            return False,f"Wrong Type,Ban Pc!"
        #check team funds and wage
        team_row = self.teams_df.loc[self.teams_df["club_id"] == bidding_team]
        team = team_row.iloc[0]
        if team["budget"]< bid_amount:
            return False, f"Player {player_id} not enough budget."
        if team["wage"] < wage:
            return False, f"Player {player_id} not enough wage."
        if bid_amount < int(player["starting_bid"]):
            return False, f"Player {player_id} not enough starting bid."
        return True, None

    def create_bid(self, player_id, bid_amount,wage, bidding_team):
        # Validate that player and team exist
        if player_id not in self.players_df["player_id"].values:
            print(f"Player ID {player_id} not found.")
            return None, f"Player {player_id} not found.",None
        if bidding_team not in self.teams_df["club_id"].values:
            print(f"Team '{bidding_team}' not found.")
            return None, f"Team '{bidding_team}' not found.",None
        is_valid,message = self.can_bid_be_placed(player_id, bid_amount, bidding_team, wage)
        if is_valid == False:
            return None, message,None

        new_bid = Bids(player_id, bid_amount, wage ,bidding_team,
                       teams_df=self.teams_df, players_df=self.players_df,typeo="Regular")

        self.bids.append(new_bid)
        current_team = self.players_df.loc[ self.players_df["player_id"] == player_id, 'club_name'].iloc[0]
        #print(self.teams_df.loc[self.teams_df["club_id"]==241])
        self.teams_df.loc[self.teams_df["club_id"]==bidding_team, 'budget'] -= bid_amount
        self.teams_df.loc[self.teams_df["club_id"] == bidding_team, 'wage'] -= wage
        #print(self.teams_df.loc[self.teams_df["club_id"] == 241])


        selling_team_mask = self.teams_df["club_name"] == current_team
        print(self.teams_df.loc[selling_team_mask, 'budget'])
        self.teams_df.loc[selling_team_mask, 'budget'] += bid_amount
        print(self.teams_df.loc[selling_team_mask, 'budget'])
        self.teams_df.loc[selling_team_mask, 'wage'] += self.players_df.loc[ self.players_df["player_id"] == player_id, 'wage'].iloc[0]
        self.players_df.loc[self.players_df["player_id"] == player_id, "starting_bid"] = bid_amount
        print(f" Created bid for player {player_id} by {bidding_team}.")
        past_bidders_list = self.players_df.loc[self.players_df["player_id"] == player_id, 'past_bidders'].item()
        print(past_bidders_list)
        if past_bidders_list:
            for b in self.bids:
                if b.player_id == player_id and b.time_remaining == 0:
                    return None, f"Player {player_id} too late (ban pc).",None
            self.remove_bid(player_id,"Regular")
        #else:
           # self.teams_df.loc[selling_team_mask, 'wage'] += self.players_df.loc[self.players_df["player_id"] == player_id, 'wage']
        self.players_df.loc[self.players_df["player_id"] == player_id]["past_bidders"].item().append(bidding_team)
        self.players_df.loc[self.players_df["player_id"] == player_id, "is_listed"] = False
        return new_bid, f'Created bid for {self.players_df.loc[self.players_df["player_id"] == player_id, "name"].item()} by {self.teams_df.loc[self.teams_df["club_id"] == bidding_team, "club_name"].item()}.',past_bidders_list
    def get_active_bids(self):
        return [b for b in self.bids if b.is_active()]

    def remove_bid(self,player_id,type):
        for b in self.bids:
            if b.player_id == player_id:
                self.bids.remove(b)
                b.deactivate_bid()
                print(b.outgoing_team)
                self.teams_df.loc[self.teams_df["club_id"] == b.bidding_team, "budget"] += b.bid
                self.teams_df.loc[self.teams_df["club_id"] == b.outgoing_team, "budget"] -= b.bid if type == "Regular" or type == "Regular Loan" else 0
                self.teams_df.loc[self.teams_df["club_id"] == b.bidding_team, "wage"] += b.wage
                self.teams_df.loc[self.teams_df["club_id"] == b.outgoing_team, "wage"] -= self.players_df.loc[self.players_df["player_id"] == player_id, 'wage'].iloc[0]




    def cleanup_expired(self): #also can be used to get the expired bids
        expired_bids = [b for b in self.bids if not b.is_active()]
        self.bids = [b for b in self.bids if b.is_active()]

        if not expired_bids:
            print("No expired bids to clean up.")
            return
        df = pd.DataFrame([{
            "player_id": b.player_id,
            "bidding_team": b.bidding_team,
            "outgoing_team": b.outgoing_team,
            "bid": b.bid,
            "wage": b.wage,
            "start_time": b.starting_time,
            "end_time": b.ending_time,
            "expired_at": datetime.now(),
            "type":b.typeo
        } for b in expired_bids])

        os.makedirs("expired_bids", exist_ok=True)
        filename = f"expired_bids/expired_bids_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        df.to_csv(filename, index=False)

        print(f" Saved {len(expired_bids)} expired bids to '{filename}' and cleaned up memory.")

    def list_player(self,player_id,team_id,bid,typeo):
        if player_id not in self.players_df["player_id"].values:
            return False, f"Player {player_id} not found."
        if team_id not in self.teams_df["club_id"].values:
            return False, f"Team '{team_id}' not found."
        past_bidders_list = self.players_df.loc[self.players_df["player_id"] == player_id, 'past_bidders'].item()
        if past_bidders_list:
            return False, f"Player {player_id} already getting bid on (ban pc)."
        player_row = self.players_df.loc[self.players_df["player_id"] == player_id]
        player = player_row.iloc[0]
        if player["club_id"] != team_id:
            return False, f"Player {player_id} is not in your team."
        self.players_df.loc[self.players_df["player_id"] == player_id,'is_listed'] = True
        self.players_df.loc[self.players_df["player_id"] == player_id, 'starting_bid'] = bid
        if typeo != "Regular" and typeo != "Free Loan" and typeo != "Dev Loan" and typeo != "Paid Loan":
            return False, "unrecognized type (ban pc)"
        else:
            self.players_df.loc[self.players_df["player_id"] == player_id, 'Type'] = typeo
        return True, f"Player {player_id} is now listed."


    def unlist_player(self,player_id,team_id):
        if player_id not in self.players_df["player_id"].values:
            return False, f"Player {player_id} not found."
        if team_id not in self.teams_df["club_id"].values:
            return False, f"Team '{team_id}' not found."
        player_row = self.players_df.loc[self.players_df["player_id"] == player_id]
        player = player_row.iloc[0]
        if player["club_id"] != team_id:
            return False, f"Player {player_id} is not in your team."
        self.players_df.loc[self.players_df["player_id"] == player_id,'is_listed'] = False
        self.players_df.loc[self.players_df["player_id"] == player_id, 'starting_bid'] = None
        return True, f"Player {player_id} is now unlisted."

    def get_listed_players(self):
        return self.players_df.loc[self.players_df["is_listed"] == True]

    def dev_loan_bid(self, player_id, bid_amount,wage, bidding_team):
        player_row = self.players_df.loc[self.players_df["player_id"] == player_id]
        past_bidders_list = self.players_df.loc[self.players_df["player_id"] == player_id, 'past_bidders'].item()
        if player_row.empty:
            return False, f"Player {player_id} not found."
        player = player_row.iloc[0]
        if not (player["is_listed"]):
            for b in self.bids:
                if b.player_id == player_id:
                    if not b.is_active:
                        return False, f"Player {player_id} not listed."
        if player["is_listed"] != True:
            return False, f"Player {player_id} not listed."
        #check team funds and wage
        team_row = self.teams_df.loc[self.teams_df["club_id"] == bidding_team]
        team = team_row.iloc[0]
        if team["wage"] < wage:
            return False, f"Player {player_id} not enough wage."
        if player_id not in self.players_df["player_id"].values:
            print(f"Player ID {player_id} not found.")
            return None, f"Player {player_id} not found."
        if bidding_team not in self.teams_df["club_id"].values:
            print(f"Team '{bidding_team}' not found.")
            return None, f"Team '{bidding_team}' not found."

        new_bid = Bids(player_id, 0, wage, bidding_team,
                       teams_df=self.teams_df, players_df=self.players_df, typeo="Dev Loan")

        self.bids.append(new_bid)
        current_team = self.players_df.loc[self.players_df["player_id"] == player_id, 'club_name'].iloc[0]
        # print(self.teams_df.loc[self.teams_df["club_id"]==241])
        self.teams_df.loc[self.teams_df["club_id"] == bidding_team, 'budget'] -= bid_amount
        self.teams_df.loc[self.teams_df["club_id"] == bidding_team, 'wage'] -= wage
        # print(self.teams_df.loc[self.teams_df["club_id"] == 241])

        selling_team_mask = self.teams_df["club_name"] == current_team
        print(self.teams_df.loc[selling_team_mask, 'budget'])
        self.teams_df.loc[selling_team_mask, 'budget'] += bid_amount
        print(self.teams_df.loc[selling_team_mask, 'budget'])
        self.teams_df.loc[selling_team_mask, 'wage'] += wage
        self.players_df.loc[self.players_df["player_id"] == player_id, "starting_bid"] = bid_amount
        print(f" Created bid for player {player_id} by {bidding_team}.")
        print(past_bidders_list)
        if past_bidders_list:
            for b in self.bids:
                if b.player_id == player_id and b.time_remaining == 0:
                    return None, f"Player {player_id} too late (ban pc)."
            self.remove_bid(player_id,"Dev Loan")
        # else:
        # self.teams_df.loc[selling_team_mask, 'wage'] += self.players_df.loc[self.players_df["player_id"] == player_id, 'wage']
        self.players_df.loc[self.players_df["player_id"] == player_id]["past_bidders"].item().append(bidding_team)
        self.players_df.loc[self.players_df["player_id"] == player_id, "is_listed"] = False
        return new_bid, f'Created bid for {self.players_df.loc[self.players_df["player_id"] == player_id, "name"].item()} by {self.teams_df.loc[self.teams_df["club_id"] == bidding_team, "club_name"].item()}.'


    def create_free_loan_bid(self, player_id, bid_amount,wage, bidding_team):
        player_row = self.players_df.loc[self.players_df["player_id"] == player_id]
        if player_row.empty:
            return False, f"Player {player_id} not found.",None
        player = player_row.iloc[0]
        if not (player["is_listed"]):
            for b in self.bids:
                if b.player_id == player_id:
                    if not b.is_active:
                        return False, f"Player {player_id} not listed.",None
        if player["Type"] != "Free Loan":
            return False,f"Wrong Type,Ban Pc!",None
        #check team funds and wage
        team_row = self.teams_df.loc[self.teams_df["club_id"] == bidding_team]
        team = team_row.iloc[0]
        if team["budget"]< bid_amount:
            return False, f"Player {player_id} not enough budget.",None
        if team["wage"] < wage:
            return False, f"Player {player_id} not enough wage.",None
        if bid_amount < int(player["starting_bid"]):
            return False, f"Player {player_id} not enough starting bid.",None
        # Validate that player and team exist
        if player_id not in self.players_df["player_id"].values:
            print(f"Player ID {player_id} not found.")
            return None, f"Player {player_id} not found.",None
        if bidding_team not in self.teams_df["club_id"].values:
            print(f"Team '{bidding_team}' not found.")
            return None, f"Team '{bidding_team}' not found.",None

        new_bid = Bids(player_id, bid_amount, wage ,bidding_team,
                       teams_df=self.teams_df, players_df=self.players_df,typeo="Free Loan")

        self.bids.append(new_bid)
        current_team = self.players_df.loc[ self.players_df["player_id"] == player_id, 'club_name'].iloc[0]
        #print(self.teams_df.loc[self.teams_df["club_id"]==241])
        self.teams_df.loc[self.teams_df["club_id"]==bidding_team, 'budget'] -= bid_amount
        self.teams_df.loc[self.teams_df["club_id"] == bidding_team, 'wage'] -= wage
        #print(self.teams_df.loc[self.teams_df["club_id"] == 241])


        selling_team_mask = self.teams_df["club_name"] == current_team
        print(self.teams_df.loc[selling_team_mask, 'budget'])
        self.teams_df.loc[selling_team_mask, 'budget'] += 0
        print(self.teams_df.loc[selling_team_mask, 'budget'])
        self.teams_df.loc[selling_team_mask, 'wage'] += wage
        self.players_df.loc[self.players_df["player_id"] == player_id, "starting_bid"] = bid_amount
        print(f" Created bid for player {player_id} by {bidding_team}.")
        past_bidders_list = self.players_df.loc[self.players_df["player_id"] == player_id, 'past_bidders'].item()
        print(past_bidders_list)
        if past_bidders_list:
            for b in self.bids:
                if b.player_id == player_id and b.time_remaining == 0:
                    return None, f"Player {player_id} too late (ban pc).",None
            self.remove_bid(player_id,"Free Loan")
        #else:
           # self.teams_df.loc[selling_team_mask, 'wage'] += self.players_df.loc[self.players_df["player_id"] == player_id, 'wage']
        self.players_df.loc[self.players_df["player_id"] == player_id]["past_bidders"].item().append(bidding_team)
        self.players_df.loc[self.players_df["player_id"] == player_id, "is_listed"] = False
        return new_bid, f'Created bid for {self.players_df.loc[self.players_df["player_id"] == player_id, "name"].item()} by {self.teams_df.loc[self.teams_df["club_id"] == bidding_team, "club_name"].item()}.',past_bidders_list

    def create_reg_loan_bid(self, player_id, bid_amount,wage, bidding_team):
        player_row = self.players_df.loc[self.players_df["player_id"] == player_id]
        if player_row.empty:
            return False, f"Player {player_id} not found.",None
        player = player_row.iloc[0]
        if not (player["is_listed"]):
            for b in self.bids:
                if b.player_id == player_id:
                    if not b.is_active:
                        return False, f"Player {player_id} not listed.",None
        if player["Type"] != "Regular Loan":
            return False,f"Wrong Type,Ban Pc!",None
        #check team funds and wage
        team_row = self.teams_df.loc[self.teams_df["club_id"] == bidding_team]
        team = team_row.iloc[0]
        if team["budget"]< bid_amount:
            return False, f"Player {player_id} not enough budget.",None
        if team["wage"] < wage:
            return False, f"Player {player_id} not enough wage.",None
        if bid_amount < int(player["starting_bid"]):
            return False, f"Player {player_id} not enough starting bid.",None
        # Validate that player and team exist
        if player_id not in self.players_df["player_id"].values:
            print(f"Player ID {player_id} not found.")
            return None, f"Player {player_id} not found.",None
        if bidding_team not in self.teams_df["club_id"].values:
            print(f"Team '{bidding_team}' not found.")
            return None, f"Team '{bidding_team}' not found.",None


        new_bid = Bids(player_id, bid_amount, wage ,bidding_team,
                       teams_df=self.teams_df, players_df=self.players_df,typeo="Free Loan")

        self.bids.append(new_bid)
        current_team = self.players_df.loc[ self.players_df["player_id"] == player_id, 'club_name'].iloc[0]
        #print(self.teams_df.loc[self.teams_df["club_id"]==241])
        self.teams_df.loc[self.teams_df["club_id"]==bidding_team, 'budget'] -= bid_amount
        self.teams_df.loc[self.teams_df["club_id"] == bidding_team, 'wage'] -= wage
        #print(self.teams_df.loc[self.teams_df["club_id"] == 241])


        selling_team_mask = self.teams_df["club_name"] == current_team
        print(self.teams_df.loc[selling_team_mask, 'budget'])
        self.teams_df.loc[selling_team_mask, 'budget'] += bid_amount
        print(self.teams_df.loc[selling_team_mask, 'budget'])
        self.teams_df.loc[selling_team_mask, 'wage'] += wage
        self.players_df.loc[self.players_df["player_id"] == player_id, "starting_bid"] = bid_amount
        print(f" Created bid for player {player_id} by {bidding_team}.")
        past_bidders_list = self.players_df.loc[self.players_df["player_id"] == player_id, 'past_bidders'].item()
        print(past_bidders_list)
        if past_bidders_list:
            for b in self.bids:
                if b.player_id == player_id and b.time_remaining == 0:
                    return None, f"Player {player_id} too late (ban pc).",None
            self.remove_bid(player_id,"Free Loan")
        #else:
           # self.teams_df.loc[selling_team_mask, 'wage'] += self.players_df.loc[self.players_df["player_id"] == player_id, 'wage']
        self.players_df.loc[self.players_df["player_id"] == player_id]["past_bidders"].item().append(bidding_team)
        self.players_df.loc[self.players_df["player_id"] == player_id, "is_listed"] = False

        return new_bid, f'Created bid for {self.players_df.loc[self.players_df["player_id"] == player_id, "name"].item()} by {self.teams_df.loc[self.teams_df["club_id"] == bidding_team, "club_name"].item()}.',past_bidders_list


    def get_info(self,team_id):
        budget = self.teams_df.loc[team_id, "budget"]
        wage = self.teams_df.loc[team_id, "wage"]
        return budget, wage