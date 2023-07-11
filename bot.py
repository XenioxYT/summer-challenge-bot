import discord
from discord import commands
from discord.ext import commands
from discord import bot
from discord import ui
import os
import random
import sqlite3
import typing
from fuzzywuzzy import process
from dotenv import load_dotenv
import asyncio

load_dotenv()
TOKEN = os.getenv('DISCORD_TOKEN')

intents = discord.Intents.all()
intents.typing = False
intents.presences = True
intents.messages = True
intents.guilds = True
intents.members = True

bot = commands.Bot(application_command_prefix='!', intents=intents, help_command=None, case_insensitive=True)

@bot.event
async def on_ready():
    print(f'Logged in as {bot.user}')
    bot.intents.members = True

@bot.application_command(name='help', help='Display a list of all commands and what they do.')
async def help(ctx):
    help_embed = discord.Embed(title="Bot Commands", color=discord.Color.blue())
    
    help_embed.description = """
**!add_challenge / !newChallenge [challenge] [points]**
_Adds a challenge if it doesn't already exist._
Example: `!add_challenge "challenge name" 10`
You can add multiple challenges at once by separating them with commas. 
Example: `!add_challenge "challenge1", "challenge2", "challenge3" 10`

**/all_challenges**
_Lists all challenges._

**/user_stats**
_Get a user's stats._

**!random_challenge / !surpriseMe [user]**
_Get a random challenge for a user._

**!complete / !finishChallenge [challenge]**
_Mark a challenge as completed for a user._

**!leaderboard / !showRankings**
_Show the leaderboard._

**!progress / !checkProgress [user1] [user2] ...**
_Show the progress of a user or a group of users._

**!remaining / !pendingChallenges [user]**
_Show the remaining challenges for a user._

**!search / !findChallenge [keyword]**
_Search for challenges._

**!delete_challenge / !removeChallenge / !discardChallenge [challenge]**
_Delete a challenge._
Example: `!delete_challenge [challenge name]`

**!help**
_Display this message._
    """
    
    await ctx.response.send_message(embed=help_embed)



def challenge_formatter(index, challenge_data):
    challenge_name, points = challenge_data
    return f'{index + 1}. **{challenge_name}** for `{points} points`\n'


@bot.application_command(name='add_challenge', aliases=['newChallenge'], help='Adds challenges: !add_challenge "challenge1", "challenge2", "challenge3" points')
async def add_challenge(ctx, challenges: str, points: int): # use separate arguments for challenges and points
    try:
        challenges = [s.strip().strip('"') for s in challenges.split(',')]  # Strip the quotes from the challenge strings
    except ValueError:
        await ctx.response.send_message('Invalid input format. Please follow the format: "challenge1", "challenge2", "challenge3" points') # use response.send_message instead of send
        return

    conn = sqlite3.connect('challenges.db')
    c = conn.cursor()

    added_challenges = []
    for challenge in challenges:
        c.execute("SELECT * FROM challenges WHERE LOWER(challenge_name) = ?", (challenge.lower(),))
        if c.fetchone() is None:
            c.execute("INSERT INTO challenges (challenge_name, points) VALUES (?, ?)", (challenge, points))
            added_challenges.append((challenge, points, 'added'))
        else:
            added_challenges.append((challenge, points, 'already exists'))

    conn.commit()
    conn.close()

    def formatter(i, data):
        challenge, points, status = data
        emoji = '✅' if status == 'added' else '❌'
        return f'{i+1}. {emoji} **{challenge}** for `{points} points` {status}\n'

    paginator = AddChallengePaginator(ctx, added_challenges, "Added challenges", formatter)
    await paginator.start()



@bot.application_command(name='delete_challenge', aliases=['removeChallenge', 'discardChallenge'], help='Deletes a challenge: !delete_challenge "challenge1"')
@discord.commands.default_permissions(manage_messages=True) # only members with manage messages permission can use this command
async def delete_challenge(ctx, *, challenge: str):
    challenge = challenge.strip('"')  # Strip the quotes from the challenge string
    conn = sqlite3.connect('challenges.db')
    c = conn.cursor()
    
    c.execute("SELECT * FROM challenges WHERE LOWER(challenge_name) = ?", (challenge.lower(),))
    if c.fetchone() is None:
        await ctx.response.send_message(f'The challenge "{challenge}" does not exist.') # use response.send_message instead of send
    else:
        c.execute("DELETE FROM challenges WHERE LOWER(challenge_name) = ?", (challenge.lower(),))
        await ctx.response.send_message(f'The challenge "{challenge}" has been deleted.') # use response.send_message instead of send
        
    conn.commit()
    conn.close()


@bot.application_command(name='search', aliases=['findChallenge'], help='Search for challenges: !search keyword')
async def search(ctx, *, keyword: str):
    conn = sqlite3.connect('challenges.db')
    c = conn.cursor()

    # Get all challenge names
    c.execute("SELECT challenge_name FROM challenges")
    all_challenges = [row[0] for row in c.fetchall()]

    # Get the top 5 matches to the keyword
    matches = process.extract(keyword, all_challenges, limit=20)

    # Now get the full data for those top matches
    results = []
    for match, score in matches:
        if score >= 50:  # Set a minimum score
            c.execute("SELECT challenge_name, points FROM challenges WHERE challenge_name = ?", (match,))
            results.append(c.fetchone())

    conn.close()

    if results:
        paginator = ChallengePaginator(ctx, results, f'Challenge search results for "{keyword}"', challenge_formatter)
        await paginator.start()
    else:
        await ctx.response.send_message(f'No challenges found similar to "{keyword}"') # use response.send_message instead of send



@bot.application_command(name='all_challenges', aliases=['showAllChallenges'], help='Lists all challenges.')
async def all_challenges(ctx):
    conn = sqlite3.connect('challenges.db')
    c = conn.cursor()
    c.execute("SELECT challenge_name, points FROM challenges ORDER BY points DESC")
    all_challenges = c.fetchall()
    conn.close()

    def formatter(i, data):
        challenge, points = data
        emoji = '🏆' if points >= 100 else '🎖️' if points >= 50 else '🎗️'
        return f'{i+1}. {emoji} **{challenge}** for `{points} points`\n'

    paginator = ChallengePaginator(ctx, all_challenges, "All Challenges", formatter)
    await paginator.start()

def get_color(completed_points):
    # Connect to the database
    conn = sqlite3.connect('challenges.db')
    c = conn.cursor()

    # Get the total points of all challenges
    c.execute("SELECT SUM(points) FROM challenges")
    total_points = c.fetchone()[0]

    # Close the connection
    conn.close()

    # Calculate the percentage of completed points
    percentage = completed_points / total_points

    # Return a different color depending on the percentage
    if percentage >= 0.5: # more than 50% completed
        return discord.Color.green()
    elif percentage >= 0.25: # more than 25% completed
        return discord.Color.gold()
    else: # less than 25% completed
        return discord.Color.red()

@bot.application_command(name='user_stats', aliases=['getUserStats'], help='Get a user\'s stats: !user_stats [user] [detail]')
async def user_stats(ctx, user: discord.User = None, detail: bool = False): # type: ignore
    if user is None:
        user = ctx.author
    conn = sqlite3.connect('challenges.db')
    c = conn.cursor()
    # Get total points
    c.execute("""
        SELECT SUM(challenges.points)
        FROM user_progress
        INNER JOIN challenges ON user_progress.challenge_id = challenges.challenge_id
        WHERE user_progress.user_id = ? AND user_progress.is_completed = ?
    """, (user.id, True))
    total_points = c.fetchone()[0]

    # Get completed challenges
    c.execute("""
        SELECT challenges.challenge_name, challenges.points
        FROM user_progress
        INNER JOIN challenges ON user_progress.challenge_id = challenges.challenge_id
        WHERE user_progress.user_id = ? AND user_progress.is_completed = ?
    """, (user.id, True))
    completed_challenges = c.fetchall()

    # Get completed points
    c.execute("""
        SELECT SUM(challenges.points)
        FROM user_progress
        INNER JOIN challenges ON user_progress.challenge_id = challenges.challenge_id
        WHERE user_progress.user_id = ? AND user_progress.is_completed = ?
    """, (user.id, True))
    completed_points = c.fetchone()[0]

    conn.close()

    # Create embed
    color=get_color(completed_points) # use completed points instead of completed challenges
    embed = discord.Embed(title=f"{user.name}'s Stats", color=discord.Color.blue())
    embed.set_thumbnail(url=user.avatar.url)
    embed.add_field(name="__Total Points__", value=f"{total_points or 0} 🏆", inline=True)
    embed.add_field(name="__Completed Challenges__", value=f"{len(completed_challenges) or 0} 🏁", inline=True)
    embed.color = color

    if completed_challenges:
        recent_challenge_name, recent_challenge_points = completed_challenges[-1]

        sorted_challenges = sorted(completed_challenges, key=lambda x: x[1], reverse=True)
        challenges_list = [f"{name} ({points} points)" for name, points in sorted_challenges]
        
        if detail: # check if the user wants to see the detailed stats
            paginator = Paginator(challenges_list) # create a paginator object with the challenges list
            page_number = 1 # start from the first page
            page_content = paginator.get_page(page_number) # get the content of the first page

            field_value = "\n".join(page_content) # join the content with newlines
            embed.add_field(name=f"__Challenge List (Page {page_number} of {paginator.get_max_pages()})__", value=f"{field_value}", inline=False) # add the field value to the embed

            # Add a field for the most recent challenge completed
            embed.add_field(name="__Most Recent Challenge Completed__", value=f"{recent_challenge_name} ({recent_challenge_points} points) 🎉", inline=False)

            message = await ctx.response.send_message(embed=embed) # send the message with the embed

            await message.add_reaction("⬅️") # add a reaction for going back a page
            await message.add_reaction("➡️") # add a reaction for going forward a page

            def check(reaction, user): # define a check function for the reaction event
                return user == ctx.author and reaction.message.id == message.id and str(reaction.emoji) in ["⬅️", "➡️"] # check if the reaction is from the author and on the same message and is one of the valid emojis
            
            while True: # loop until break
                try:
                    reaction, user = await bot.wait_for("reaction_add", timeout=60.0, check=check) # wait for a reaction that passes the check within 60 seconds
                except asyncio.TimeoutError: # if no reaction is added within 60 seconds
                    await message.clear_reactions() # clear all reactions from the message
                    break # break the loop
                else: # if a valid reaction is added
                    if str(reaction.emoji) == "⬅️": # if the reaction is for going back a page
                        page_number -= 1 # decrement the page number by 1
                        if page_number < 1: # if the page number is less than 1
                            page_number = paginator.get_max_pages() # wrap around to the last page
                        
                        page_content = paginator.get_page(page_number) # get the content of the new page
                        field_value = "\n".join(page_content) # join the content with newlines
                        embed.set_field_at(2, name=f"__Challenge List (Page {page_number} of {paginator.get_max_pages()})__", value=f"{field_value}") # update the field value in the embed
                        await message.edit(embed=embed) # edit the message with the new embed
                        await message.remove_reaction(reaction, user) # remove the reaction from the message
                    elif str(reaction.emoji) == "➡️": # if the reaction is for going forward a page
                        page_number += 1 # increment the page number by 1
                        if page_number > paginator.get_max_pages(): # if the page number is greater than the max pages
                            page_number = 1 # wrap around to the first page
                        
                        page_content = paginator.get_page(page_number) # get the content of the new page
                        field_value = "\n".join(page_content) # join the content with newlines
                        embed.set_field_at(2, name=f"__Challenge List (Page {page_number} of {paginator.get_max_pages()})__", value=f"{field_value}") # update the field value in the embed
                        await message.edit(embed=embed) # edit the message with the new embed
                        await message.remove_reaction(reaction, user) # remove the reaction from the message

        else: # if the user does not want to see the detailed stats
            # Add a field for the most recent challenge completed
            embed.add_field(name="__Most Recent Challenge Completed__", value=f"{recent_challenge_name} ({recent_challenge_points} points) 🎉", inline=False)
            await ctx.response.send_message(embed=embed) # send the message with the embed

    else:
        embed.add_field(name="\u200b", value="\u200b", inline=False)
        embed.add_field(name="__Challenge List__", value="No completed challenges 🙁", inline=False)
        await ctx.response.send_message(embed=embed)



@bot.application_command(name='random_challenge', aliases=['surpriseMe'], help='Get a random challenge for a user: !random_challenge user')
async def random_challenge(ctx, user: discord.User = None): # type: ignore
    if user is None:
        user = ctx.author
    conn = sqlite3.connect('challenges.db')
    c = conn.cursor()
    c.execute("""
        SELECT challenge_name, points
        FROM challenges
        WHERE challenge_id NOT IN (
            SELECT challenge_id FROM user_progress WHERE user_id = ? AND is_completed = ?
        )
    """, (user.id, True))
    results = c.fetchall()
    if results:
        random_challenge = random.choice(results)
        challenge_name, points = random_challenge
        remaining_challenges = len(results) - 1

        # Choose a color for the embed based on the points of the challenge
        if points >= 100:
            color = discord.Color.red()
        elif points >= 50:
            color = discord.Color.gold()
        else:
            color = discord.Color.green()

        # Create an embed to display the challenge name and points
        embed = discord.Embed(title=f"A random challenge for {user.name}", color=color)
        embed.add_field(name="__Challenge Name__", value=f"**{challenge_name}**", inline=False)
        embed.add_field(name="__Points__", value=f"`{points}`", inline=False)
        embed.add_field(name="__Remaining Challenges__", value=f"`{remaining_challenges}`", inline=False)

        await ctx.response.send_message(embed=embed) # use response.send_message instead of send
    else:
        await ctx.response.send_message(f'{user.name} has completed all challenges.') # use response.send_message instead of send
    conn.close()

@bot.application_command(name='complete', aliases=['finishChallenge'], help='Mark a challenge as completed for a user: !complete challenge1, challenge2, challenge3')
async def complete(ctx, user: typing.Optional[discord.User] = None, *, challenges: str = None):
    if user is None:
        user = ctx.author
    if challenges is None:
        await ctx.response.send_message('No challenges provided.') # use response.send_message instead of send
        return
    challenge_names = [challenge.strip().lower() for challenge in challenges.split(',')]  # Split challenges by comma and strip whitespace

    conn = sqlite3.connect('challenges.db')
    c = conn.cursor()

    completed_challenges = []
    for challenge in challenge_names:
        c.execute("SELECT challenge_id, points FROM challenges WHERE LOWER(challenge_name) = ?", (challenge,))
        result = c.fetchone()
        if result is None:
            completed_challenges.append((challenge, 'not found'))
            continue
        challenge_id, points = result
        c.execute("INSERT OR IGNORE INTO user_progress (user_id, challenge_id, is_completed) VALUES (?, ?, ?)", (user.id, challenge_id, False))
        c.execute("SELECT is_completed FROM user_progress WHERE user_id = ? AND challenge_id = ?", (user.id, challenge_id))
        is_completed = c.fetchone()[0]
        if is_completed:
            completed_challenges.append((challenge, 'already completed'))
            continue
        c.execute("UPDATE user_progress SET is_completed = ? WHERE user_id = ? AND challenge_id = ?", (True, user.id, challenge_id))
        completed_challenges.append((challenge, 'completed'))

    conn.commit()
    conn.close()

    def formatter(i, data):
        challenge, status = data
        emoji = '✅' if status == 'completed' else '❌'
        return f'{i+1}. {emoji} **{challenge}** {status}\n'

    paginator = CompleteChallengePaginator(ctx, completed_challenges, "Completed Challenges", formatter)
    await paginator.start()


@bot.application_command(name='leaderboard', aliases=['showRankings'], help='Show the leaderboard: !leaderboard')
async def leaderboard(ctx):
    conn = sqlite3.connect('challenges.db')
    c = conn.cursor()
    c.execute("""
        SELECT user_id, SUM(challenges.points)
        FROM user_progress
        INNER JOIN challenges ON user_progress.challenge_id = challenges.challenge_id
        WHERE user_progress.is_completed = ?
        GROUP BY user_id
        ORDER BY SUM(challenges.points) DESC
    """, (True,))
    results = c.fetchall()
    conn.close()
    leaderboard_embed = discord.Embed(title="Leaderboard", color=discord.Color.blue())

    # Define a dictionary of emojis and colors for each rank
    rank_emojis = {1: '👑', 2: '🥈', 3: '🥉'}
    rank_colors = {1: discord.Color.gold(), 2: discord.Color.light_gray(), 3: discord.Color.dark_orange()}

    for i, (user_id, total_points) in enumerate(results, start=1):
        user = await bot.fetch_user(user_id)

        # Get the emoji and color for the current rank, or use default values if not in the dictionary
        emoji = rank_emojis.get(i, '⭐')
        color = rank_colors.get(i, discord.Color.blue())

        # Create a field for each user with their name, points, and emoji
        leaderboard_embed.add_field(name=f"{emoji} {user.name}", value=f"{total_points or 0} points", inline=False)

        # Change the color of the embed to match the current rank
        leaderboard_embed.color = color

    if len(results) == 0:
        leaderboard_embed.description = 'The leaderboard is empty.'
    await ctx.response.send_message(embed=leaderboard_embed) # use response.send_message instead of send

class AddChallengePaginator(ui.View): # subclass ui.View

    def __init__(self, ctx, data, title, formatter):
        super().__init__() # call the super constructor
        self.ctx = ctx
        self.data = data
        self.current_page = 0
        self.title = title
        self.formatter = formatter

    @discord.ui.button(label="◀️ Previous Page", style=discord.ButtonStyle.primary) # create a button with label "Previous" and style primary
    async def previous(self, button, interaction): # define a callback function for the button
        if self.current_page > 0: # check if there is a previous page
            self.current_page -= 1 # decrement the current page index
            await interaction.response.edit_message(embed=self.make_embed()) # edit the message with the previous page

    @discord.ui.button(label="Next Page ▶️", style=discord.ButtonStyle.primary) # create another button with label "Next" and style primary
    async def next(self, button, interaction): # define another callback function for the button
        if self.current_page < (len(self.data) - 1) // 10: # check if there is a next page
            self.current_page += 1 # increment the current page index
            await interaction.response.edit_message(embed=self.make_embed()) # edit the message with the next page

    async def start(self):
        if not self.data:
            await self.ctx.response.send_message('No data to display.')
            return

        self.message = await self.ctx.response.send_message(embed=self.make_embed(), view=self) # send a message with the embed and the view
        # remove the reaction code

    def make_embed(self):
        embed = discord.Embed(
            title=self.title,
            color=discord.Color.blue(),
            description="",
        )
        for i in range(self.current_page * 10, min((self.current_page + 1) * 10, len(self.data))):
            embed.description += self.formatter(i, self.data[i])

        total_pages = (len(self.data) + 9) // 10
        embed.set_footer(text=f"Page {self.current_page + 1} of {total_pages}")

        return embed



class ChallengePaginator(ui.View): # subclass ui.View

    def __init__(self, ctx, challenges, title, formatter):
        super().__init__() # call the super constructor
        self.ctx = ctx
        self.challenges = challenges
        self.current_page = 0
        self.title = title
        self.formatter = formatter

    @discord.ui.button(label="◀️ Previous Page", style=discord.ButtonStyle.primary) # create a button with label "Previous" and style primary
    async def previous(self, button, interaction): # define a callback function for the button
        if self.current_page > 0: # check if there is a previous page
            self.current_page -= 1 # decrement the current page index
            await interaction.response.edit_message(embed=self.make_embed()) # edit the message with the previous page

    @discord.ui.button(label="Next Page ▶️", style=discord.ButtonStyle.primary) # create another button with label "Next" and style primary
    async def next(self, button, interaction): # define another callback function for the button
        if self.current_page < (len(self.challenges) - 1) // 10: # check if there is a next page
            self.current_page += 1 # increment the current page index
            await interaction.response.edit_message(embed=self.make_embed()) # edit the message with the next page

    async def start(self):
        if not self.challenges:
            await self.ctx.response.send_message('No challenges exist yet.')
            return

        self.message = await self.ctx.response.send_message(embed=self.make_embed(), view=self) # send a message with the embed and the view
        # remove the reaction code

    def make_embed(self):
        embed = discord.Embed(
            title=self.title,
            color=discord.Color.blue(),
            description="",
        )
        for i in range(self.current_page * 10, min((self.current_page + 1) * 10, len(self.challenges))):
            challenge_data = self.challenges[i]
            embed.description += self.formatter(i, challenge_data) # type: ignore

        total_pages = (len(self.challenges) + 9) // 10
        embed.set_footer(text=f"Page {self.current_page + 1} of {total_pages}")

        return embed
    
class Paginator:
    def __init__(self, items, page_size=10):
        self.items = items # the list of items to paginate
        self.page_size = page_size # the number of items per page
        self.max_pages = (len(items) - 1) // page_size + 1 # the total number of pages
    
    def get_page(self, page_number):
        # return a sublist of items for the given page number
        start_index = (page_number - 1) * self.page_size # the start index of the sublist
        end_index = start_index + self.page_size # the end index of the sublist
        return self.items[start_index:end_index] # return the sublist
    
    def get_max_pages(self):
        # return the maximum number of pages
        return self.max_pages



class CompleteChallengePaginator(AddChallengePaginator):
    def __init__(self, ctx, data, title, formatter):
        super().__init__(ctx, data, title, formatter)

@bot.application_command(name='progress', aliases=['checkProgress'], help='Show the progress of a user or a group of users: !progress [user1] [user2] ...')
async def progress(ctx, *users: discord.User):
    if not users:
        # If no users are given, use the author of the message
        users = (ctx.author,)
    conn = sqlite3.connect('challenges.db')
    c = conn.cursor()

    # Get the total number of challenges
    c.execute("SELECT COUNT(*) FROM challenges")
    total_challenges = c.fetchone()[0]

    # Create an empty list to store the progress data for each user
    progress_data = []

    # Create an empty dictionary to store the winner data
    winner_data = {"user": None, "points": 0, "challenges": 0}

    for user in users:
        # Get the number of completed challenges and total points for each user
        c.execute("""
            SELECT COUNT(*), SUM(challenges.points)
            FROM user_progress
            INNER JOIN challenges ON user_progress.challenge_id = challenges.challenge_id
            WHERE user_progress.user_id = ? AND user_progress.is_completed = ?
        """, (user.id, True))
        completed_challenges, total_points = c.fetchone()

        # Calculate the percentage of completed challenges
        percentage = round(completed_challenges / total_challenges * 100, 2)

        # Append a tuple of user name, points, completed challenges, and percentage to the progress data list
        progress_data.append((user.name, total_points or 0, completed_challenges or 0, percentage))

        # Use a try-except block to handle the TypeError when comparing None with an integer
        try:
            # Update the winner data if the current user has more points or completed challenges than the previous winner
            if total_points > winner_data["points"] or (total_points == winner_data["points"] and completed_challenges > winner_data["challenges"]):
                winner_data["user"] = user.name
                winner_data["points"] = total_points
                winner_data["challenges"] = completed_challenges
        except TypeError:
            # If total_points is None, use 0 as the default value for comparison
            if 0 > winner_data["points"] or (0 == winner_data["points"] and completed_challenges > winner_data["challenges"]):
                winner_data["user"] = user.name
                winner_data["points"] = 0
                winner_data["challenges"] = completed_challenges

    conn.close()

    # Choose a color for the embed based on who is the winner
    if len(users) == 1:
        # If only one user is given, use blue as the default color
        color = discord.Color.blue()
    elif len(set(progress_data)) == 1:
        # If all users have the same progress data, use yellow as the color for a tie
        color = discord.Color.gold()
    elif winner_data["user"] == ctx.author.name:
        # If the author of the message is the winner, use green as the color for a win
        color = discord.Color.green()
    else:
        # Otherwise, use red as the color for a loss
        color = discord.Color.red()

    # Create an embed to show the progress of each user
    embed = discord.Embed(title="Progress Report", color=color)
    
    # Define some symbols and abbreviations for formatting
    point_symbol = '🏅'
    challenge_symbol = '🎯'
    percent_emoji = '📈'
    percent_symbol = '%'
    point_abbrev = 'pts'
    challenge_abbrev = 'challenges'

    for name, points, challenges, percent in progress_data:
        # Create a field for each user with their name and formatted progress data
        field_value = f"{point_symbol} {points} {point_abbrev}\n{challenge_symbol} {challenges}/{total_challenges} {challenge_abbrev}\n{percent_emoji} {percent} {percent_symbol}"
        embed.add_field(name=f"{name}", value=field_value, inline=True)

    if len(users) > 1:
        # If more than one user is given, add a field to show who is the winner or if there is a tie
        if len(set(progress_data)) == 1:
            # If all users have the same progress data, show a tie message
            embed.add_field(name="Result", value="It's a tie!", inline=False)
        else:
            # Otherwise, show the winner's name and progress data
            winner_value = f"{point_symbol} {winner_data['points']} {point_abbrev}\n{challenge_symbol} {winner_data['challenges']}/{total_challenges} {challenge_abbrev}"
            embed.add_field(name="Winner", value=f"{winner_data['user']}\n{winner_value}", inline=False)

    await ctx.response.send_message(embed=embed)

@bot.application_command(name='remaining', aliases=['pendingChallenges'], help='Show the remaining challenges for a user: !remaining [user]')
async def remaining(ctx, user: discord.User = None): # type: ignore
    if user is None:
        user = ctx.author
    conn = sqlite3.connect('challenges.db')
    c = conn.cursor()
    c.execute("""
        SELECT challenge_name, points
        FROM challenges
        WHERE challenge_id NOT IN (
            SELECT challenge_id FROM user_progress WHERE user_id = ? AND is_completed = ?
        )
        ORDER BY points DESC
    """, (user.id, True))
    results = c.fetchall()
    conn.close()

    def formatter(i, data):
        challenge, points = data
        emoji = '🏆' if points >= 100 else '🎖️' if points >= 50 else '🎗️'
        return f'{i+1}. {emoji} **{challenge}** for `{points} points`\n'

    paginator = ChallengePaginator(ctx, results, f'Remaining challenges for {user.name}', formatter)
    await paginator.start()

bot.run(TOKEN) # type: ignore

