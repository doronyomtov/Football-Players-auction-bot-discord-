import discord
from discord.ext import commands
from discord import app_commands
import os
import pandas as pd
from dotenv import load_dotenv
import math


from Data_loader import data_loader, teams_df
from AuctionManager import AuctionManager

def number(num):
    return f"{int(num):,}"


class PaginationView(discord.ui.View):
    """A class to create paginated embeds with interactive buttons."""
    def __init__(self, interaction: discord.Interaction, data: list, title: str, items_per_page: int = 5):
        super().__init__(timeout=180)  # View times out after 180 seconds of inactivity
        self.interaction = interaction
        self.data = data
        self.title = title
        self.items_per_page = items_per_page
        self.current_page = 0
        # Calculate the total number of pages needed
        self.total_pages = math.ceil(len(self.data) / self.items_per_page)

    async def send_initial_message(self):
        """Sends the first page of the embed."""
        self.update_buttons()
        embed = self.create_embed()

        if self.interaction.response.is_done():
            await self.interaction.followup.send(embed=embed, view=self)
        else:
            await self.interaction.response.send_message(embed=embed, view=self)
        self.message = await self.interaction.original_response()

    def create_embed(self) -> discord.Embed:

        start_index = self.current_page * self.items_per_page
        end_index = start_index + self.items_per_page
        page_data = self.data[start_index:end_index]

        embed = discord.Embed(
            title=f"{self.title} (Page {self.current_page + 1}/{self.total_pages})",
            color=discord.Color.blue()
        )

        if not page_data:
            embed.description = "There are no items on this page."
        else:
            description_lines = []

            if self.title == "Currently Listed Players":
                for p in page_data:
                    description_lines.append(
                        f"**{p['name']}** (ID: {int(p['player_id'])})\n"
                        f"> Starting Bid: £{number(p['starting_bid'])} | Type: `{p['Type']}`"
                    )
            elif self.title == "Active Bids":
                 for b in page_data:
                    description_lines.append(
                        f"**{b.player_name}** (ID: {b.player_id})\n"
                        f"> Bid: £{number(b.bid)} by **{b.bidding_team}**\n"
                        f"> Wage: £{number(b.wage)} | Type: `{b.typeo}`\n"
                        f"> Time Left: {b.time_remaining()}"
                    )
            embed.description = "\n\n".join(description_lines)

        embed.set_footer(text=f"Showing items {start_index + 1}-{min(end_index, len(self.data))} of {len(self.data)}")
        return embed

    def update_buttons(self):
        """Disables/enables buttons based on the current page."""
        # The first child is the 'Previous' button, the second is 'Next'
        self.children[0].disabled = self.current_page == 0
        self.children[1].disabled = self.current_page >= self.total_pages - 1

    @discord.ui.button(label="◀ Previous", style=discord.ButtonStyle.secondary)
    async def previous_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Callback for the 'Previous' button."""
        self.current_page -= 1
        self.update_buttons()
        embed = self.create_embed()
        await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(label="Next ▶", style=discord.ButtonStyle.secondary)
    async def next_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Callback for the 'Next' button."""
        self.current_page += 1
        self.update_buttons()
        embed = self.create_embed()
        await interaction.response.edit_message(embed=embed, view=self)


def setUp():
    """
    Initializes the auction system by loading player and team data and creating the AuctionManager.

    :returns manager: the initialized AuctionManager instance ~class
    """
    try:
        players_df_loaded, teams_df_loaded = data_loader()
    except FileNotFoundError as e:
        raise Exception(f"Setup Failed: Could not find required CSV file: {e}. Ensure all data files are present.")

    if 'teams' in teams_df_loaded.columns:
        teams_df_loaded = teams_df_loaded.rename(columns={"teams": "team_name"})

    manager = AuctionManager(teams_df_loaded, players_df_loaded)
    return manager


def create_bid(manager, player_id: int, bid_amount: int, bidding_team: int, wage: int):
    """
    Attempts to create a bid on a listed player.

    :param manager: the auction manager instance created by setUp() ~class
    :param player_id: the ID of the player being bid on ~int
    :param bid_amount: the amount of the bid ~int
    :param bidding_team: the ID of the team placing the bid (e.g., team ID or password) ~int
    :param wage: the amount of wage being offered (manual entry for now) ~int

    :returns msg: accordingly if created the bid or if didn't (the msg contains the reason why it didn't) ~str
    """
    _,msg,past_bidders  = manager.create_bid(player_id, bid_amount, wage,bidding_team)
    return msg,past_bidders


def list_player(manager, player_id: int, team_id: int, bid: int,typeo: str):
    """
    Lists a player for auction (only listed players can be bid on).

    :param manager: the auction manager instance created by setUp() ~class
    :param player_id: the ID of the player to list ~ int
    :param team_id: the ID of the team listing the player ~int
    :param bid: the amount of the starting bid ~int
    :param typeo: the type of the starting bid ~str (Regular,Dev Loan, Paid Loan, Free Loan)
    :returns msg: accordingly if created the bid ~str
    """
    _, msg = manager.list_player(player_id, team_id, bid,typeo)
    return msg


def unlist_player(manager, player_id: int, team_id: int):
    """
    Unlists a player. Currently, the main way to change a player's starting bid.

    :param manager: the auction manager instance created by setUp() ~class
    :param player_id: the ID of the player to unlist ~int
    :param team_id: the ID of the team unlisting the player ~int

    :returns msg: accordingly if the player was unlisted ~str
    """
    _, msg = manager.unlist_player(player_id, team_id)
    return msg


def get_listed_players(manager):
    """
    Returns a list of all players who are currently listed in the auction.

    :param manager: the auction manager instance created by setUp() ~class

    :returns list of players: who are listed in the auction manager ~list of dicts
    """
    lst = manager.get_listed_players()
    print(lst)
    return lst


def clean_memory(manager):
    """
    Cleans up memory by removing expired auctions and creates a CSV file of finished auctions (in the real implementation).

    :param manager: the auction manager instance created by setUp() ~class

    :returns status_msg: a message confirming the cleanup ~str
    """
    manager.cleanup_expired()
    return " **Cleanup Complete:** Expired auctions have been processed and memory has been reset."


def active_bid_list(manager):
    """
    Returns a list of all active bids on currently listed players.

    :param manager: the auction manager instance created by setUp() ~class

    :returns list of active bids: ~list of dicts
    """
    lst = manager.get_active_bids()
    print(f"Active bids {lst}")
    return lst


def remove_bid(manager, player_id: int,typeo: str):
    """
    Deletes the active bid for a specific player.

    :param manager: the auction manager instance created by setUp() ~class
    :param player_id: the ID of the player whose bid should be removed ~int
    :param typeo: the type of the bid should be removed ~str
    :returns msg: a message confirming the bid removal ~str
    """
    manager.remove_bid(player_id, typeo)
    return f"Player {player_id} removed bid {typeo}"

def create_dev_bid(manager, player_id: int, bid_amount: int, bidding_team: int, wage: int):
    """
    Attempts to create a bid on a listed player.

    :param manager: the auction manager instance created by setUp() ~class
    :param player_id: the ID of the player being bid on ~int
    :param bid_amount: the amount of the bid ~int
    :param bidding_team: the ID of the team placing the bid (e.g., team ID or password) ~int
    :param wage: the amount of wage being offered (manual entry for now) ~int

    :returns msg: accordingly if created the bid or if didn't (the msg contains the reason why it didn't) ~str
    """
    _, msg = manager.dev_loan_bid(player_id, bid_amount, wage,bidding_team)
    return msg

def create_free_loan_bid(manager, player_id: int, bid_amount: int, bidding_team: int, wage: int):
    """
    Attempts to create a bid on a listed player.

    :param manager: the auction manager instance created by setUp() ~class
    :param player_id: the ID of the player being bid on ~int
    :param bid_amount: the amount of the bid ~int
    :param bidding_team: the ID of the team placing the bid (e.g., team ID or password) ~int
    :param wage: the amount of wage being offered (manual entry for now) ~int

    :returns msg: accordingly if created the bid or if didn't (the msg contains the reason why it didn't) ~str
    """
    _, msg,past_bidders = manager.create_free_loan_bid(player_id, bid_amount, wage,bidding_team)
    return msg,past_bidders

def create_reg_loan_bid(manager, player_id: int, bid_amount: int, bidding_team: int, wage: int):
    """
    Attempts to create a bid on a listed player.

    :param manager: the auction manager instance created by setUp() ~class
    :param player_id: the ID of the player being bid on ~int
    :param bid_amount: the amount of the bid ~int
    :param bidding_team: the ID of the team placing the bid (e.g., team ID or password) ~int
    :param wage: the amount of wage being offered (manual entry for now) ~int

    :returns msg: accordingly if created the bid or if didn't (the msg contains the reason why it didn't) ~str
    """
    _, msg,past_bidders = manager.create_reg_loan_bid(player_id, bid_amount, wage,bidding_team)
    return msg,past_bidders

def get_info(manager,team_id):
    budget,wage = manager.get_info(team_id)
    return budget, wage


# --- Discord Bot Implementation ---

# Set up the bot with necessary intents
class AuctionBot(commands.Bot):
    def __init__(self):
        # We need message content intent to process standard commands, but
        # since we focus on slash commands, fewer intents are needed.
        self.teams_df = pd.read_csv("team_df.csv")
        intents = discord.Intents.default()
        super().__init__(command_prefix='!', intents=intents)
        self.manager = None  # AuctionManager instance will be stored here

    async def on_ready(self):
        print(f'Logged in as {self.user} (ID: {self.user.id})')
        await self.tree.sync()
        print('Synced application commands.')
        print('---')

        # Optional: Auto-run setup on bot start
        try:
            self.manager = setUp()
            print("AuctionManager setup successful on bot startup.")
        except Exception as e:
            print(f"Setup failed on startup: {e}")


bot = AuctionBot()


# --- Slash Command Definitions ---

@bot.tree.command(name="setup_auction", description="Initializes the Auction Manager and loads player/team data.")
@app_commands.describe(
    admin_pass="admin password")
async def setup_command(interaction: discord.Interaction,admin_pass: str):
    """
    Initializes the auction system by loading player and team data and creating the AuctionManager.

    :returns manager: the initialized AuctionManager instance ~class
    """
    await interaction.response.defer(ephemeral=True)
    if admin_pass !="ufl2025":
        await interaction.followup.send("Nice try, Ban PC!")
        return None
    try:
        bot.manager = setUp()
        team_count = len(bot.manager.teams_df)
        player_count = len(bot.manager.players_df)

        embed = discord.Embed(
            title=" Auction System Initialized",
            description=f"The auction manager has been set up successfully with initial data.",
            color=discord.Color.green()
        )
        embed.add_field(name="Teams Loaded", value=f"{team_count} teams found", inline=True)
        embed.add_field(name="Players Loaded", value=f"{player_count} players found", inline=True)

        await interaction.followup.send(embed=embed)

    except Exception as e:
        await interaction.followup.send(f" **SETUP FAILED:** {e}", ephemeral=True)


@bot.tree.command(name="list_player", description="Lists a player for auction with a starting bid.")
@app_commands.describe(
    player_id="The ID of the player you want to list (e.g., 101)",
    team_id="Your team's ID or unique code (e.g., 201)",
    starting_bid="The minimum starting bid amount (e.g., 500)",
    type = "Regular,Dev Loan, Paid Loan, Free Loan"
)
async def list_player_command(interaction: discord.Interaction, player_id: int, team_id: int, starting_bid: int, type:str):
    """
    Lists a player for auction (only listed players can be bid on).

    :param manager: the auction manager instance created by setUp() ~class
    :param player_id: the ID of the player to list ~ int
    :param team_id: the ID of the team listing the player ~int
    :param bid: the amount of the starting bid ~int

    :returns msg: accordingly if created the bid ~str
    """
    if not bot.manager:
        return await interaction.response.send_message("❌ Auction system is not set up. Run `/setup_auction` first.",
                                                       ephemeral=True)

    msg = list_player(bot.manager, player_id, team_id, starting_bid,type)
    await interaction.response.send_message(msg)


@bot.tree.command(name="bid", description="Place a new bid on a currently listed player.")
@app_commands.describe(
    player_id="The ID of the player you want to bid on (must be listed)",
    bid_amount="The total amount of the bid",
    bidding_team="Your team's ID or unique code (e.g., 201)",
    wage="The player's proposed wage component of the bid",
)
async def create_bid_command(interaction: discord.Interaction, player_id: int, bid_amount: int, bidding_team: int,
                             wage: int):
    """
    Attempts to create a bid on a listed player.

    :param manager: the auction manager instance created by setUp() ~class
    :param player_id: the ID of the player being bid on ~int
    :param bid_amount: the amount of the bid ~int
    :param bidding_team: the ID of the team placing the bid (e.g., team ID or password) ~int
    :param wage: the amount of wage being offered (manual entry for now) ~int

    :returns msg: accordingly if created the bid or if didn't (the msg contains the reason why it didn't) ~str
    """
    if not bot.manager:
        return await interaction.response.send_message(" Auction system is not set up. Run `/setup_auction` first.",
                                                       ephemeral=True)

    msg,past_bidders = create_bid(bot.manager, player_id, bid_amount, bidding_team, wage)
    print(f'past_bidders: {past_bidders}')
    if past_bidders:
        if len(past_bidders) > 1:
            for i in past_bidders:
                print(teams_df)
                print(i)
                discord_id= teams_df.loc[teams_df["club_id"] == i, "discord_id"].iloc[0]
                print(discord_id)
                await send_direct_message(bot,discord_id,msg)

    await interaction.response.send_message(msg)


@bot.tree.command(name="unlist_player", description="Removes a player from the auction.")
@app_commands.describe(
    player_id="The ID of the player to unlist",
    team_id="Your team's ID (for verification/tracking)",
)
async def unlist_player_command(interaction: discord.Interaction, player_id: int, team_id: int):
    """
    Unlists a player (player need to be listed (i think) currently the only way to change player starting bid (don't ask me to find other way pls)

    :param manager: the auction manager instance created by setUp() ~class
    :param player_id: the ID of the player who wants to unbid ~int
    :param team_id: the ID of the team who wants to unbid ~int
    :return msg accordingly if created the bid ~str
    """
    if not bot.manager:
        return await interaction.response.send_message(" Auction system is not set up. Run `/setup_auction` first.",
                                                       ephemeral=True)

    msg = unlist_player(bot.manager, player_id, team_id)
    await interaction.response.send_message(msg)


@bot.tree.command(name="listed_players", description="Shows all players currently available for bidding.")
async def get_listed_players_command(interaction: discord.Interaction):
    """
    Returns a paginated list of all players who are listed in the auction.
    """
    if not bot.manager:
        await interaction.response.send_message("Auction system is not set up. Run `/setup_auction` first.", ephemeral=True)
        return

    listed = get_listed_players(bot.manager)

    if listed.empty:
        await interaction.response.send_message("No players are currently listed for auction.")
        return

    # Convert the DataFrame to a list of dictionaries to pass to the pagination view
    listed_players_data = listed.to_dict('records')

    # Create an instance of our pagination view and send it
    view = PaginationView(interaction, listed_players_data, "Currently Listed Players")
    await view.send_initial_message()


@bot.tree.command(name="active_bids", description="Shows all active bids on listed players.")
async def active_bid_list_command(interaction: discord.Interaction):
    """
    Returns a paginated list of all active bids.
    """
    if not bot.manager:
        await interaction.response.send_message("Auction system is not set up. Run `/setup_auction` first.", ephemeral=True)
        return

    active_bids = active_bid_list(bot.manager)

    if not active_bids:
        await interaction.response.send_message("There are no active bids right now.")
        return

    # Create an instance of our pagination view and send it
    view = PaginationView(interaction, active_bids, "Active Bids")
    await view.send_initial_message()


@bot.tree.command(name="remove_bid", description="Deletes the active bid for a specific player.")
@app_commands.describe(
    player_id="The ID of the player whose bid you want to remove",
    type ="Regular,Dev Loan, Paid Loan, Free Loan"
)
async def remove_bid_command(interaction: discord.Interaction, player_id: int,type: str):
    """
    Deletes a bid for a specific player.

    :param manager: the auction manager instance created by setUp() ~class
    :param player_id: the ID of the player whose bid should be removed ~int
    :param type: the type of the bid you wish to remove
    :return: a message confirming the bid removal ~str
    """
    if not bot.manager:
        return await interaction.response.send_message(" Auction system is not set up. Run `/setup_auction` first.",
                                                       ephemeral=True)

    msg = remove_bid(bot.manager, player_id,type)
    await interaction.response.send_message(msg)


@bot.tree.command(name="cleanup", description="Cleans up expired auctions and resets memory.")
async def clean_memory_command(interaction: discord.Interaction):
    """
    Cleans memory and creates a CSV file of finished auctions (in the real implementation).

    :param manager: the auction manager instance created by setUp() ~class

    :returns status_msg: a message confirming the cleanup ~str
    """
    if not bot.manager:
        return await interaction.response.send_message("Auction system is not set up. Run `/setup_auction` first.",
                                                       ephemeral=True)

    msg = clean_memory(bot.manager)
    await interaction.response.send_message(msg)



@bot.tree.command(name="dev_bid", description="Place a new dev loan bid on a currently listed player.")
@app_commands.describe(
    player_id="The ID of the player you want to bid on (must be listed)",
    bid_amount="The total amount of the bid",
    bidding_team="Your team's ID or unique code (e.g., 201)",
    wage="The player's proposed wage component of the bid",
)
async def create_dev_loan_bid_command(interaction: discord.Interaction, player_id: int, bid_amount: int, bidding_team: int,
                             wage: int):
    """
    Attempts to create a bid on a listed player.

    :param manager: the auction manager instance created by setUp() ~class
    :param player_id: the ID of the player being bid on ~int
    :param bid_amount: the amount of the bid ~int
    :param bidding_team: the ID of the team placing the bid (e.g., team ID or password) ~int
    :param wage: the amount of wage being offered (manual entry for now) ~int

    :returns msg: accordingly if created the bid or if didn't (the msg contains the reason why it didn't) ~str
    """
    if not bot.manager:
        return await interaction.response.send_message(" Auction system is not set up. Run `/setup_auction` first.",
                                                       ephemeral=True)

    msg = create_dev_bid(bot.manager, player_id, bid_amount, bidding_team, wage)
    await interaction.response.send_message(msg)

@bot.tree.command(name="free_loan_bid", description="Place a new free loan bid on a currently listed player.")
@app_commands.describe(
    player_id="The ID of the player you want to bid on (must be listed)",
    bid_amount="The total amount of the bid",
    bidding_team="Your team's ID or unique code (e.g., 201)",
    wage="The player's proposed wage component of the bid",
)
async def create_free_loan_bid_command(interaction: discord.Interaction, player_id: int, bid_amount: int, bidding_team: int,
                             wage: int):
    """
    Attempts to create a bid on a listed player.

    :param manager: the auction manager instance created by setUp() ~class
    :param player_id: the ID of the player being bid on ~int
    :param bid_amount: the amount of the bid ~int
    :param bidding_team: the ID of the team placing the bid (e.g., team ID or password) ~int
    :param wage: the amount of wage being offered (manual entry for now) ~int

    :returns msg: accordingly if created the bid or if didn't (the msg contains the reason why it didn't) ~str
    """
    if not bot.manager:
        return await interaction.response.send_message(" Auction system is not set up. Run `/setup_auction` first.",
                                                       ephemeral=True)

    msg,past_bidders = create_free_loan_bid(bot.manager, player_id, bid_amount, bidding_team, wage)
    print(f'past_bidders: {past_bidders}')
    await interaction.response.send_message(msg)


@bot.tree.command(name="regular_loan_bid", description="Place a new Regular loan bid on a currently listed player.")
@app_commands.describe(
    player_id="The ID of the player you want to bid on (must be listed)",
    bid_amount="The total amount of the bid",
    bidding_team="Your team's ID or unique code (e.g., 201)",
    wage="The player's proposed wage component of the bid",
)
async def create_regular_loan_bid_command(interaction: discord.Interaction, player_id: int, bid_amount: int, bidding_team: int,
                             wage: int):
    """
    Attempts to create a bid on a listed player.

    :param manager: the auction manager instance created by setUp() ~class
    :param player_id: the ID of the player being bid on ~int
    :param bid_amount: the amount of the bid ~int
    :param bidding_team: the ID of the team placing the bid (e.g., team ID or password) ~int
    :param wage: the amount of wage being offered (manual entry for now) ~int

    :returns msg: accordingly if created the bid or if didn't (the msg contains the reason why it didn't) ~str
    """
    if not bot.manager:
        return await interaction.response.send_message(" Auction system is not set up. Run `/setup_auction` first.",
                                                       ephemeral=True)

    msg,past_bidders = create_reg_loan_bid(bot.manager, player_id, bid_amount, bidding_team, wage)
    print(f"past_bidders: {past_bidders}")
    await interaction.response.send_message(msg)

@bot.tree.command(name="info", description="Get Info about your budget and wage")
@app_commands.describe(
    team_id="The ID of the team you want to show info about",
)
async def get_info_command(interaction: discord.Interaction, team_id: int):
    """
    Get info about your budget and wage

    :param team_id: the ID of the team you want to show info about
    """
    if not bot.manager:
        return await interaction.response.send_message(" Auction system is not set up. Run `/setup_auction` first.",
                                                       ephemeral=True)

    budget,wage = get_info(bot.manager, team_id)
    msg = f"Team Budget: {number(budget)}\nTeam Wage: {number(wage)}"
    await interaction.response.send_message(msg)


async def send_direct_message(bot: commands.Bot, user_id: int, message_content: str):
    """
    Sends a direct message to a Discord user.

    Args:
        bot (commands.Bot): The bot client instance.
        user_id (int): The Discord ID of the user to message.
        message_content (str): The message to send.

    Returns:
        bool: True if the message was sent successfully, False otherwise.
    """
    try:
        user = await bot.fetch_user(user_id)

        if user is None:
            print(f"Error: Could not find user with ID {user_id}.")
            return False

        # 2. Send the message to the user
        await user.send(message_content)
        print(f"Successfully sent DM to {user.name} (ID: {user_id}).")
        return True

    except discord.Forbidden:
        # This occurs if the user has disabled DMs from server members/bots
        # or has blocked the bot.
        print(f"Error: Cannot send DM to user {user_id}. DMs may be disabled.")
        return False
    except discord.HTTPException as e:
        # Other potential issues, like rate limits or message too long
        print(f"An HTTP error occurred while sending DM to {user_id}: {e}")
        return False
    except Exception as e:
        # Catch any other unexpected errors
        print(f"An unexpected error occurred: {e}")
        return False

load_dotenv()
token = os.environ.get("DISCORD_BOT_ID")
bot.run(token)

