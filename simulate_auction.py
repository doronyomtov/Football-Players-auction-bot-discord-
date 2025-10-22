import unittest
import pandas as pd
import numpy as np
import os
import shutil
import time

# --- ASSUMED IMPORTS ---
from AuctionManager import AuctionManager
from Bids import Bids
from Data_loader import data_loader, players_df  # Import the data loader function


class TestAuctionManager(unittest.TestCase):

    def setUp(self):
        # Load data using the provided data_loader
        # NOTE: We assume data_loader returns (processed_players_df, merged_teams_df)
        try:
            players_df_loaded, teams_df_loaded = data_loader()
        except FileNotFoundError as e:
            raise Exception(f"Setup Failed: Could not find required CSV file: {e}. Ensure all data files are present.")

        # The teams_df_loaded contains a 'teams' column from the CSV,
        # which needs to be renamed to 'team_name' to match AuctionManager's lookup logic.
        if 'teams' in teams_df_loaded.columns:
            teams_df_loaded = teams_df_loaded.rename(columns={"teams": "team_name"})

        # Instantiate the AuctionManager
        # Use a copy of players_df to avoid side effects during testing
        self.manager = AuctionManager(teams_df_loaded, players_df_loaded.copy())

        # --- Define Actual Data Points for Testing (Using Kylian Mbappé data) ---
        self.PLAYER_ID = 231747  # Kylian Mbappé (from Sample_Data.csv)
        self.TEAM_A_ID = 243  # Mbappé's Club (Selling Team)
        self.TEAM_B_ID = 241  # Bidding Team id #barca (Need sufficient budget/wage)
        self.TEAM_C_ID = 9 #liverpool
        # Get initial budgets for comparison
        try:
            self.initial_budget_A = \
            self.manager.teams_df.loc[self.manager.teams_df["club_id"] == self.TEAM_A_ID, "budget"].iloc[0]
            self.initial_budget_B = \
            self.manager.teams_df.loc[self.manager.teams_df["club_id"] == self.TEAM_B_ID, "budget"].iloc[0]
        except IndexError:
            raise Exception(
                "Setup Error: Could not find required test teams (Real Madrid or FC Barcelona) in the loaded data. Check Data_loader logic.")

    def tearDown(self):
        # Clean up the directory created by AuctionManager.cleanup_expired if it exists
        pass
        #if os.path.exists("expired_bids"):
            #shutil.rmtree("expired_bids")

    ## 1) Making a transfer list for a team
    def test_list_player_success(self):
        # Player 231747 (Mbappé) lists himself from Real Madrid
        bid_amount = 1000000
        success, message = self.manager.list_player(
            player_id=self.PLAYER_ID,
            team_id=self.TEAM_A_ID,
            bid=bid_amount
        )
        self.assertTrue(success, f"Listing failed: {message}")

        # Verify DataFrame update
        player_row = self.manager.players_df.loc[self.manager.players_df["player_id"] == self.PLAYER_ID].iloc[0]
        self.assertTrue(player_row["is_listed"])
        self.assertEqual(player_row["starting_bid"], bid_amount)

    ## 2) Show the transfer list
    def test_get_listed_players(self):
        # List Player 231747
        self.manager.list_player(player_id=self.PLAYER_ID, team_id=self.TEAM_A_ID, bid=1000000)

        listed_players = self.manager.get_listed_players()

        self.assertEqual(len(listed_players), 1)
        self.assertEqual(listed_players.iloc[0]["player_id"], self.PLAYER_ID)

    ## 3) Bidding (includes budget transfer test)
    def test_create_bid_success_and_budget_transfer(self):
        # 1. Setup: List Player (Mbappe)
        self.manager.list_player(player_id=self.PLAYER_ID, team_id=self.TEAM_A_ID, bid=1000000)

        bid_amount = 5000000
        new_wage = 10000


        budget_B_before = \
        self.manager.teams_df.loc[self.manager.teams_df["club_id"] == self.TEAM_B_ID, "budget"].iloc[0]
        budget_A_before = \
        self.manager.teams_df.loc[self.manager.teams_df["club_id"] == self.TEAM_A_ID, "budget"].iloc[0]
        bid = self.manager.create_bid(
            player_id=self.PLAYER_ID,
            bid_amount=bid_amount,
            wage=new_wage,
            bidding_team=self.TEAM_B_ID
        )

        self.assertIsNotNone(bid)

        budget_B_after = \
        self.manager.teams_df.loc[self.manager.teams_df["club_id"] == self.TEAM_B_ID, "budget"].iloc[0]

        budget_A_after = \
        self.manager.teams_df.loc[self.manager.teams_df["club_id"] == self.TEAM_A_ID, "budget"].iloc[0]

        print(f'budget_B_before {budget_B_before} budget_b_after {budget_B_after} bid = {bid}')
        print(f'budget_A_before {budget_A_before} budget_a_after {budget_A_after} bid = {bid}')
        self.assertEqual(budget_B_after, budget_B_before - bid_amount,
                         "Bidding team budget failed to decrease correctly.")
        print("aaa" ,budget_A_after )
        self.assertEqual(budget_A_after, budget_A_before + bid_amount,
                         "Selling team budget failed to increase correctly.")

    ## 4) Showing active bids
    def test_get_active_bids_and_cleanup(self):
        # Setup: List Player 231747
        self.manager.list_player(player_id=self.PLAYER_ID, team_id=self.TEAM_A_ID, bid=1000000)

        # Create two bids (Manchester United is assumed to have enough funds)
        TEAM_C_id = 11
        self.manager.create_bid(self.PLAYER_ID, 5000000, 10000, self.TEAM_B_ID)
        self.manager.create_bid(self.PLAYER_ID, 6000000, 12000, TEAM_C_id)

        # Check active bids immediately after creation (they should all be active due to 12h timer)
        active_bids = self.manager.get_active_bids()
        print(f"active bids:",active_bids)
        self.assertEqual(len(active_bids), 1)

        # Test that cleanup_expired runs without error and retains active bids (due to the 12h timer)
        self.manager.cleanup_expired()
        self.assertEqual(len(self.manager.get_active_bids()), 1)

    ## 5) Removing player from transfer list and showing it updated
    def test_unlist_player(self):
        # 1. List Player 231747
        self.manager.list_player(player_id=self.PLAYER_ID, team_id=self.TEAM_A_ID, bid=1000000)

        # 2. Unlist Player 231747
        success, message = self.manager.unlist_player(player_id=self.PLAYER_ID, team_id=self.TEAM_A_ID)

        self.assertTrue(success)

        # 3. Verify unlisted status in DataFrame and transfer list
        player_row = self.manager.players_df.loc[self.manager.players_df["player_id"] == self.PLAYER_ID].iloc[0]
        self.assertFalse(player_row["is_listed"])
        self.assertTrue(pd.isna(player_row["starting_bid"]))
        self.assertEqual(len(self.manager.get_listed_players()), 0)

    def test_buy_below_initial_bid_failure(self):
        # 1. Define the initial bid and a too-low bid
        INITIAL_BID = 10000000
        LOW_BID = 9000000
        WAGE = 10000

        # 2. Setup: List Player with the required INITIAL_BID
        self.manager.list_player(
            player_id=self.PLAYER_ID,
            team_id=self.TEAM_A_ID,
            bid=INITIAL_BID
        )

        # 3. Attempt to bid less than the starting bid
        is_valid, message = self.manager.can_bid_be_placed(
            player_id=self.PLAYER_ID,
            bid_amount=LOW_BID,
            bidding_team=self.TEAM_B_ID,
            wage=WAGE
        )
        print(is_valid, message)
        # 4. Assert that the bid is NOT valid
        self.assertFalse(is_valid, f"Bid should have failed due to low amount but passed. Message: {message}")

        # 5. Verify no bid was created
        bid,msg = self.manager.create_bid(
            player_id=self.PLAYER_ID,
            bid_amount=LOW_BID,
            wage=WAGE,
            bidding_team=self.TEAM_B_ID
        )
        print(msg)
        self.assertIsNone(bid,
                          "create_bid should return None when validity check fails (assuming internal enforcement).")

    def test_wage_update_on_bid(self):
        INITIAL_BID = 10000000
        WAGE = 100000  # Player's weekly wage
        PLAYER_ID = self.PLAYER_ID
        TEAM_A_ID = self.TEAM_A_ID  # Selling Team
        TEAM_B_ID = self.TEAM_B_ID  # Bidding Team

        # Get Initial Wages
        initial_wage_A = self.manager.teams_df.loc[self.manager.teams_df["club_id"] == TEAM_A_ID, "wage"].iloc[0]
        initial_wage_B = self.manager.teams_df.loc[self.manager.teams_df["club_id"] == TEAM_B_ID, "wage"].iloc[0]

        # List Player
        self.manager.list_player(
            player_id=PLAYER_ID,
            team_id=TEAM_A_ID,
            bid=INITIAL_BID
        )

        # Team B places the bid
        is_valid, _ = self.manager.create_bid(
            player_id=PLAYER_ID,
            bid_amount=INITIAL_BID,
            bidding_team=TEAM_B_ID,
            wage=WAGE
        )
        self.assertTrue(is_valid, "Bid creation failed.")

        # Get Post-Bid Wages
        post_bid_wage_A = self.manager.teams_df.loc[self.manager.teams_df["club_id"] == TEAM_A_ID, "wage"].iloc[0]
        post_bid_wage_B = self.manager.teams_df.loc[self.manager.teams_df["club_id"] == TEAM_B_ID, "wage"].iloc[0]

        # Assertions
        # Bidding Team (B): Wage should decrease by player's wage
        expected_wage_B = initial_wage_B - WAGE
        # Selling Team (A): Wage should increase by player's wage (freed up)
        expected_wage_A = initial_wage_A + players_df.loc[players_df["player_id"] == PLAYER_ID, "wage"].iloc[0]
        print(expected_wage_A, initial_wage_A)

        self.assertEqual(post_bid_wage_B, expected_wage_B,
                         "Bidding team's wage was not correctly decreased.")
        self.assertEqual(post_bid_wage_A, expected_wage_A,
                         "Selling team's wage was not correctly increased.")

    def test_bid_outbidding_sequence(self):
        INITIAL_BID = 10000000
        BID_2 = 12000000  # Higher bid
        WAGE = 100000
        PLAYER_ID = self.PLAYER_ID
        TEAM_A_ID = self.TEAM_A_ID  # Selling Team
        TEAM_B_ID = self.TEAM_B_ID  # Bidder 1
        TEAM_C_ID = self.TEAM_C_ID  # Bidder 2

        # List Player
        self.manager.list_player(
            player_id=PLAYER_ID,
            team_id=TEAM_A_ID,
            bid=INITIAL_BID
        )

        # Team B places Bid 1
        bid1_obj, _ = self.manager.create_bid(
            player_id=PLAYER_ID,
            bid_amount=INITIAL_BID,
            bidding_team=TEAM_B_ID,
            wage=WAGE
        )
        self.assertTrue(bid1_obj.is_active(), "Bid 1 should be active initially.")

        # Team C places Bid 2 (Outbids Bid 1)
        bid2_obj, _ = self.manager.create_bid(
            player_id=PLAYER_ID,
            bid_amount=BID_2,
            bidding_team=TEAM_C_ID,
            wage=WAGE
        )
        self.assertTrue(bid2_obj.is_active(), "Bid 2 should be active.")

        # Check if Bid 1 has been deactivated (as 'deleted' in the user's scenario)
        self.assertFalse(bid1_obj.is_active(), "Outbid Bid 1 was not deactivated.")

        # Verify only Bid 2 is the current active bid for the player
        active_bids = [b for b in self.manager.bids if b.player_id == PLAYER_ID and b.is_active()]
        self.assertEqual(len(active_bids), 1, "There should be exactly one active bid for the player.")
        self.assertEqual(active_bids[0].bid, BID_2, "The active bid is not the latest, highest bid.")

    # 3. Check if the bid timer work correctly
    def test_bid_timer_expiration(self):
        # NOTE: Using a 3-second timer for automated test speed.
        # The underlying logic will be the same as a 30-second timer.
        TEST_DURATION = 30
        INITIAL_BID = 10000000
        WAGE = 100000
        PLAYER_ID = self.PLAYER_ID
        TEAM_A_ID = self.TEAM_A_ID  # Selling Team
        TEAM_B_ID = self.TEAM_B_ID  # Bidding Team

        self.manager.list_player(
            player_id=PLAYER_ID,
            team_id=TEAM_A_ID,
            bid=INITIAL_BID
        )

        # Team B places the bid with the short timer
        # ASSUMPTION: create_bid now accepts 'duration_seconds' (modified in AuctionManager.py)
        bid_obj, _ = self.manager.create_bid(
            player_id=PLAYER_ID,
            bid_amount=INITIAL_BID,
            bidding_team=TEAM_B_ID,
            wage=WAGE
        )

        self.assertTrue(bid_obj.is_active(), "Bid should be active initially.")

        # Wait for the bid to expire
        print(f"Waiting for {TEST_DURATION} seconds for the bid to expire...")
        time.sleep(TEST_DURATION + 1)  # Wait one second longer than the duration

        # Check if the bid is marked as inactive by the internal timer thread
        self.assertFalse(bid_obj.is_active(), "Bid did not expire after the timer ran out.")

    def test_full_auction_simulation(self):
        """
        Simulates a full auction round with multiple players, bids, and outbids,
        verifying financial accuracy and final expired bid logging.
        """
        # --- 1. SETUP ---
        print("\n" + "=" * 80)
        print("RUNNING: test_full_auction_simulation")
        print("=" * 80)

        # Player A: Kylian Mbappé (from self.setUp)
        PLAYER_A_ID = self.PLAYER_ID
        PLAYER_A_WAGE = self.manager.players_df.loc[self.manager.players_df["player_id"] == PLAYER_A_ID, "wage"].iloc[0]

        # Player B: Mohamed Salah (Assuming ID and data exist in the CSV)
        PLAYER_B_ID = 209331  # Mohamed Salah's ID
        PLAYER_B_WAGE = self.manager.players_df.loc[self.manager.players_df["player_id"] == PLAYER_B_ID, "wage"].iloc[0]

        # Teams (from self.setUp)
        TEAM_A_ID = self.TEAM_A_ID  # Seller of Player A, Buyer of Player B
        TEAM_B_ID = self.TEAM_B_ID  # Initial bidder for Player A
        TEAM_C_ID = self.TEAM_C_ID  # Outbidder for Player A, Seller of Player B

        # Record initial financial states
        initial_budget_A = self.manager.teams_df.loc[self.manager.teams_df["club_id"] == TEAM_A_ID, "budget"].iloc[0]
        initial_wage_A = self.manager.teams_df.loc[self.manager.teams_df["club_id"] == TEAM_A_ID, "wage"].iloc[0]
        initial_budget_B = self.manager.teams_df.loc[self.manager.teams_df["club_id"] == TEAM_B_ID, "budget"].iloc[0]
        initial_wage_B = self.manager.teams_df.loc[self.manager.teams_df["club_id"] == TEAM_B_ID, "wage"].iloc[0]
        initial_budget_C = self.manager.teams_df.loc[self.manager.teams_df["club_id"] == TEAM_C_ID, "budget"].iloc[0]
        initial_wage_C = self.manager.teams_df.loc[self.manager.teams_df["club_id"] == TEAM_C_ID, "wage"].iloc[0]

        print("\n--- Initial Financial State ---")
        print(f"Team A Budget: ${initial_budget_A:,.0f} | Wage: ${initial_wage_A:,.0f}")
        print(f"Team B Budget: ${initial_budget_B:,.0f} | Wage: ${initial_wage_B:,.0f}")
        print(f"Team C Budget: ${initial_budget_C:,.0f} | Wage: ${initial_wage_C:,.0f}")

        # --- 2. LISTING PHASE ---
        print("\n--- Phase 1: Listing Players ---")
        self.manager.list_player(player_id=PLAYER_A_ID, team_id=TEAM_A_ID, bid=150_000_000)
        # Note: Player B's team ID must match TEAM_C_ID in the data for this to pass
        player_b_team_id = \
        self.manager.players_df.loc[self.manager.players_df['player_id'] == PLAYER_B_ID, 'club_id'].iloc[0]
        self.manager.list_player(player_id=PLAYER_B_ID, team_id=player_b_team_id, bid=90_000_000)

        listed_players = self.manager.get_listed_players()
        print("Current Transfer List:")
        # Assuming 'short_name' column exists for better readability
        print(listed_players[['name', 'club_name', 'starting_bid']])
        self.assertEqual(len(listed_players), 2, "Should be two players on the transfer list.")

        # --- 3. BIDDING WAR FOR PLAYER A ---
        print("\n--- Phase 2: Bidding War for Player A ---")

        # Bid 1: Team B bids on Player A
        bid1_amount = 155_000_000
        bid1_wage = 400_000
        print(f"\nTeam B bids ${bid1_amount:,.0f} for Player A.")
        bid1_obj, _ = self.manager.create_bid(PLAYER_A_ID, bid1_amount, bid1_wage, TEAM_B_ID)
        print(_)
        self.assertIsNotNone(bid1_obj, "Bid 1 object should be created.")

        # Verify finances after Bid 1
        self.assertEqual(self.manager.teams_df.loc[self.manager.teams_df['club_id'] == TEAM_B_ID, 'budget'].iloc[0],
                         initial_budget_B - bid1_amount)
        self.assertEqual(self.manager.teams_df.loc[self.manager.teams_df['club_id'] == TEAM_A_ID, 'budget'].iloc[0],
                         initial_budget_A + bid1_amount)
        print(" Budgets correctly updated for Bid 1.")

        # Bid 2 (Outbid): Team C outbids Team B for Player A
        bid2_amount = 165_000_000
        bid2_wage = 420_000
        print(f"\nTeam C outbids with ${bid2_amount:,.0f} for Player A.")
        bid2_obj, _ = self.manager.create_bid(PLAYER_A_ID, bid2_amount, bid2_wage, TEAM_C_ID)
        print(_)
        self.assertIsNotNone(bid2_obj, "Bid 2 object should be created.")

        # Verify finances after outbid
        # Team B should be refunded
        self.assertEqual(self.manager.teams_df.loc[self.manager.teams_df['club_id'] == TEAM_B_ID, 'budget'].iloc[0],
                         initial_budget_B, "Team B's budget was not refunded.")
        self.assertEqual(self.manager.teams_df.loc[self.manager.teams_df['club_id'] == TEAM_B_ID, 'wage'].iloc[0],
                         initial_wage_B, "Team B's wage was not refunded.")
        print(" Team B was correctly refunded.")

        # Team C budget should decrease
        self.assertEqual(self.manager.teams_df.loc[self.manager.teams_df['club_id'] == TEAM_C_ID, 'budget'].iloc[0],
                         initial_budget_C - bid2_amount)
        # Team A budget should reflect the new, higher bid
        self.assertEqual(self.manager.teams_df.loc[self.manager.teams_df['club_id'] == TEAM_A_ID, 'budget'].iloc[0],
                         initial_budget_A + bid2_amount)
        print("Budgets for Team A and C correctly reflect the new highest bid.")

        # --- 4. STRATEGIC PURCHASE ---
        print("\n--- Phase 3: Team A uses funds to buy Player B ---")
        bid3_amount = 100_000_000
        bid3_wage = 300_000
        print(f"\nTeam A bids ${bid3_amount:,.0f} for Player B.")
        bid3_obj, _ = self.manager.create_bid(PLAYER_B_ID, bid3_amount, bid3_wage, TEAM_A_ID)
        self.assertIsNotNone(bid3_obj, "Bid 3 object should be created for Team A buying Player B.")

        # Verify final financial states before cleanup
        final_expected_budget_A = initial_budget_A + bid2_amount - bid3_amount
        final_expected_wage_A = initial_wage_A + PLAYER_A_WAGE - bid3_wage
        final_expected_budget_C = initial_budget_C - bid2_amount + bid3_amount
        final_expected_wage_C = initial_wage_C + PLAYER_B_WAGE - bid2_wage

        self.assertEqual(self.manager.teams_df.loc[self.manager.teams_df['club_id'] == TEAM_A_ID, 'budget'].iloc[0],
                         final_expected_budget_A)
        self.assertEqual(self.manager.teams_df.loc[self.manager.teams_df['club_id'] == TEAM_A_ID, 'wage'].iloc[0],
                         final_expected_wage_A)
        self.assertEqual(self.manager.teams_df.loc[self.manager.teams_df['club_id'] == TEAM_C_ID, 'budget'].iloc[0],
                         final_expected_budget_C)
        # Note: wage for C is tricky; they lose bid2_wage but gain Player B's original wage back
        self.assertEqual(self.manager.teams_df.loc[self.manager.teams_df['club_id'] == TEAM_C_ID, 'wage'].iloc[0],
                         final_expected_wage_C)
        print(" Final budgets and wages for all transactions are correct.")

        # --- 5. AUCTION CONCLUSION & CLEANUP ---
        print("\n--- Phase 4: Concluding auction and creating expired bids list ---")
        # Manually deactivate the two winning bids to simulate auction ending
        bid2_obj.deactivate_bid()
        bid3_obj.deactivate_bid()
        print("Winning bids have been manually expired.")

        self.manager.cleanup_expired()
        self.assertEqual(len(self.manager.get_active_bids()), 0, "Active bids list should be empty after cleanup.")

        # Verify CSV file was created and has the correct content
        log_dir = "expired_bids"
        self.assertTrue(os.path.exists(log_dir), "expired_bids directory was not created.")
        files = [f for f in os.listdir(log_dir) if f.endswith('.csv')]
        self.assertTrue(len(files) > 0, "No CSV log file was found in the directory.")

        latest_file = max([os.path.join(log_dir, f) for f in files], key=os.path.getctime)
        print(f"Reading expired bids from: {latest_file}")
        expired_df = pd.read_csv(latest_file)

        self.assertEqual(len(expired_df), 2, "Expired bids log should contain exactly 2 winning bids.")

        # Check that the winning bid for Player A is present
        player_a_record = expired_df[expired_df['player_id'] == PLAYER_A_ID]
        self.assertEqual(player_a_record.iloc[0]['bidding_team'], TEAM_C_ID)
        self.assertEqual(player_a_record.iloc[0]['bid'], bid2_amount)

        # Check that the winning bid for Player B is present
        player_b_record = expired_df[expired_df['player_id'] == PLAYER_B_ID]
        self.assertEqual(player_b_record.iloc[0]['bidding_team'], TEAM_A_ID)
        self.assertEqual(player_b_record.iloc[0]['bid'], bid3_amount)

        print("Expired bids CSV created and verified successfully.")
        print("\n" + "=" * 80)
        print("SUCCESS: test_full_auction_simulation")
        print("=" * 80)
if __name__ == '__main__':
    unittest.main(argv=['first-arg-is-ignored'], exit=False)