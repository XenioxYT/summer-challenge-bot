import discord
import sqlite3
import random
import os 
import math
import asyncio
import typing
from dotenv import load_dotenv
from discord.ext import commands
from discord import Embed
from fuzzywuzzy import process

# here's the list of pip packages you'll need to install
# pip install discord.py
# pip install python-dotenv
# pip install fuzzywuzzy
# pip install python-Levenshtein
# pip install discord-py-slash-command

load_dotenv()
TOKEN = os.getenv('DISCORD_TOKEN')

intents = discord.Intents.all()
intents.typing = False
intents.presences = True
intents.messages = True
intents.guilds = True
intents.members = True

bot = commands.Bot(command_prefix='!', intents=intents, help_command=None)

@bot.event
async def on_ready():
    print(f'Logged in as {bot.user}')
    bot.intents.members = True

@bot.command(name='help', help='Display a list of all commands and what they do.')
async def help(ctx):
    help_embed = discord.Embed(title="Bot Commands", color=discord.Color.blue())
    help_embed.add_field(name="!add_challenge [challenge] [points]", value="Adds a challenge if it doesn't already exist. Example: !add_challenge \"challenge name\" 10. You can add multiple challenges at once by separating them with commas. Example: !add_challenge \"challenge1\", \"challenge2\", \"challenge3\" 10")
    help_embed.add_field(name="!all_challenges", value="Lists all challenges.")
    help_embed.add_field(name="!user_stats [user]", value="Get a user's stats.")
    help_embed.add_field(name="!random_challenge [user]", value="Get a random challenge for a user.")
    help_embed.add_field(name="!complete challenge name", value="Mark a challenge as completed for a user.")
    help_embed.add_field(name="!leaderboard", value="Show the leaderboard.")
    help_embed.add_field(name="!progress [user1] [user2] ...", value="Show the progress of a user or a group of users.")
    help_embed.add_field(name="!remaining [user]", value="Show the remaining challenges for a user.")
    help_embed.add_field(name="!search [keyword]", value="Search for challenges.")
    help_embed.add_field(name="!delete_challenge [challenge]", value="Delete a challenge. Make sure to use quotes around the challenge name. Example: !delete_challenge \"challenge name\"")
    help_embed.add_field(name="!help", value="Display this message.")
    await ctx.send(embed=help_embed)


def challenge_formatter(index, challenge_data):
    challenge_name, points = challenge_data
    return f'{index + 1}. **{challenge_name}** for `{points} points`\n'


@bot.command(name='add_challenge', help='Adds challenges: !add_challenge "challenge1", "challenge2", "challenge3" points')
async def add_challenge(ctx, *, challenges_and_points: str):
    try:
        challenges_and_points = challenges_and_points.rsplit(' ', 1)
        points = int(challenges_and_points[-1])
        challenges_str = challenges_and_points[0]
        challenges = [s.strip().strip('"') for s in challenges_str.split(',')]  # Strip the quotes from the challenge strings
    except ValueError:
        await ctx.send('Invalid input format. Please follow the format: "challenge1", "challenge2", "challenge3" points')
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

@bot.command(name='delete_challenge', help='Deletes a challenge: !delete_challenge "challenge1"')
async def delete_challenge(ctx, *, challenge: str):
    challenge = challenge.strip('"')  # Strip the quotes from the challenge string
    conn = sqlite3.connect('challenges.db')
    c = conn.cursor()
    
    c.execute("SELECT * FROM challenges WHERE LOWER(challenge_name) = ?", (challenge.lower(),))
    if c.fetchone() is None:
        await ctx.send(f'The challenge "{challenge}" does not exist.')
    else:
        c.execute("DELETE FROM challenges WHERE LOWER(challenge_name) = ?", (challenge.lower(),))
        await ctx.send(f'The challenge "{challenge}" has been deleted.')
        
    conn.commit()
    conn.close()

@bot.command(name='search', help='Search for challenges: !search keyword')
async def search(ctx, *, keyword: str):
    conn = sqlite3.connect('challenges.db')
    c = conn.cursor()

    # Get all challenge names
    c.execute("SELECT challenge_name FROM challenges")
    all_challenges = [row[0] for row in c.fetchall()]

    # Get the top 5 matches to the keyword
    top_matches = process.extract(keyword, all_challenges, limit=20)

    # Now get the full data for those top matches
    results = []
    for match, score in top_matches:
        c.execute("SELECT challenge_name, points FROM challenges WHERE challenge_name = ?", (match,))
        results.append(c.fetchone())

    conn.close()

    if results:
        paginator = ChallengePaginator(ctx, results, f'Search results for "{keyword}"', challenge_formatter)
        await paginator.start()
    else:
        await ctx.send(f'No challenges found similar to "{keyword}"')


@bot.command(name='all_challenges', help='Lists all challenges.')
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

@bot.command(name='user_stats', help='Get a user\'s stats: !user_stats [user]')
async def user_stats(ctx, user: discord.User = None): # type: ignore
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
        # Get the last challenge in the list as the most recent challenge completed
        recent_challenge_name, recent_challenge_points = completed_challenges[-1]

        # Sort the completed challenges by points in descending order
        sorted_challenges = sorted(completed_challenges, key=lambda x: x[1], reverse=True)

        # Create a list of formatted challenge names and points
        challenges_list = [f"{name} ({points} points)" for name, points in sorted_challenges]

        # Split the challenge list into multiple fields, each with less than 1024 characters
        field_value = ""
        for challenge in challenges_list:
            if len(field_value) + len(challenge) + 1 > 1024: # check if adding the next challenge would exceed the limit
                embed.add_field(name="__Challenge List__", value=f"{field_value}", inline=False) # add the current field value to the embed
                field_value = "" # reset the field value
            field_value += challenge + "\n" # add the next challenge to the field value
        
        if field_value: # check if there is any remaining field value
            embed.add_field(name="__Challenge List__", value=f"{field_value}", inline=False) # add the last field value to the embed

        # Add a field for the most recent challenge completed
        embed.add_field(name="__Most Recent Challenge Completed__", value=f"{recent_challenge_name} ({recent_challenge_points} points) 🎉", inline=False)
    else:
        embed.add_field(name="\u200b", value="\u200b", inline=False)
        embed.add_field(name="__Challenge List__", value="No completed challenges 🙁", inline=False)

    await ctx.send(embed=embed)

@bot.command(name='random_challenge', help='Get a random challenge for a user: !random_challenge user')
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

        await ctx.send(embed=embed)
    else:
        await ctx.send(f'{user.name} has completed all challenges.')
    conn.close()

@bot.command(name='complete', help='Mark a challenge as completed for a user: !complete challenge name')
async def complete(ctx, user: typing.Optional[discord.User], *, challenge: str):
    global total_points  # Declare a global variable to store the total points
    if user is None:
        user = ctx.author
    challenge = challenge.lower()  # Convert to lowercase
    conn = sqlite3.connect('challenges.db')
    c = conn.cursor()
    c.execute("SELECT challenge_id, points FROM challenges WHERE LOWER(challenge_name) = ?", (challenge,))  # Convert to lowercase
    result = c.fetchone()
    if result is None:
        await ctx.send('Challenge not found.')
        return
    challenge_id, points = result
    c.execute("INSERT OR IGNORE INTO user_progress (user_id, challenge_id, is_completed) VALUES (?, ?, ?)", (user.id, challenge_id, False))
    # Add this condition to check if the user has already completed the challenge
    c.execute("SELECT is_completed FROM user_progress WHERE user_id = ? AND challenge_id = ?", (user.id, challenge_id))
    is_completed = c.fetchone()[0]
    if not is_completed:
        # Only update the table and send the message if the user has not completed the challenge
        c.execute("UPDATE user_progress SET is_completed = ? WHERE user_id = ? AND challenge_id = ?", (True, user.id, challenge_id))
        
        # Get total points
        c.execute("""
            SELECT SUM(challenges.points)
            FROM user_progress
            INNER JOIN challenges ON user_progress.challenge_id = challenges.challenge_id
            WHERE user_progress.user_id = ? AND user_progress.is_completed = ?
        """, (user.id, True))
        total_points = c.fetchone()[0]  # Assign the value to the global variable

        # Get completed challenges
        c.execute("""
            SELECT challenges.challenge_name, challenges.points
            FROM user_progress
            INNER JOIN challenges ON user_progress.challenge_id = challenges.challenge_id
            WHERE user_progress.user_id = ? AND user_progress.is_completed = ?
        """, (user.id, True))
        completed_challenges = c.fetchall()

        # Get remaining challenges
        c.execute("""
            SELECT challenge_name, points
            FROM challenges
            WHERE challenge_id NOT IN (
                SELECT challenge_id FROM user_progress WHERE user_id = ? AND is_completed = ?
            )
        """, (user.id, True))
        remaining_challenges = c.fetchall()

        conn.commit()
        conn.close()

        # Add a checkmark reaction to the message to indicate success
        await ctx.message.add_reaction('✅')

        # Create an embed to show the user's stats after completing the challenge
        embed = discord.Embed(title=f"{user.name}'s Stats", color=discord.Color.blue())
        embed.set_thumbnail(url=user.avatar.url)
        embed.add_field(name="__Total Points__", value=f"{total_points or 0}", inline=True)
        embed.add_field(name="__Completed Challenges__", value=f"{len(completed_challenges) or 0}", inline=True)
        
        if completed_challenges:
            challenges_list = '\n'.join([f"{name} ({points} points)" for name, points in completed_challenges])
            embed.add_field(name="__Challenge List__", value=f"{challenges_list}", inline=False)
        else:
            embed.add_field(name="__Challenge List__", value="No completed challenges", inline=False)

        embed.add_field(name="__Remaining Challenges__", value=f"{len(remaining_challenges) or 0}", inline=True)

        await ctx.send(embed=embed)
    else:
        # Send a different message if the user has already completed the challenge
        await ctx.send(f'{user.name} has already completed the "{challenge}" challenge.')

@bot.command(name='leaderboard', help='Show the leaderboard: !leaderboard')
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
    await ctx.send(embed=leaderboard_embed)

class AddChallengePaginator:

    def __init__(self, ctx, data, title, formatter):
        self.ctx = ctx
        self.data = data
        self.current_page = 0
        self.title = title
        self.formatter = formatter

    async def start(self):
        if not self.data:
            await self.ctx.send('No data to display.')
            return

        self.message = await self.ctx.send(embed=self.make_embed())
        await self.message.add_reaction('◀️')
        await self.message.add_reaction('▶️')

        def check(reaction, user):
            return user == self.ctx.author and str(reaction.emoji) in ['◀️', '▶️'] and reaction.message.id == self.message.id

        while True:
            try:
                reaction, user = await bot.wait_for('reaction_add', timeout=60.0, check=check)
            except asyncio.TimeoutError:
                break
            else:
                await self.message.remove_reaction(reaction, user)
                if str(reaction.emoji) == '▶️' and self.current_page < (len(self.data) - 1) // 10:
                    self.current_page += 1
                elif str(reaction.emoji) == '◀️' and self.current_page > 0:
                    self.current_page -= 1

                await self.message.edit(embed=self.make_embed())

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

class ChallengePaginator:

    def __init__(self, ctx, challenges, title, formatter):
        self.ctx = ctx
        self.challenges = challenges
        self.current_page = 0
        self.title = title
        self.formatter = formatter

    async def start(self):
        if not self.challenges:
            await self.ctx.send('No challenges exist yet.')
            return

        self.message = await self.ctx.send(embed=self.make_embed())
        await self.message.add_reaction('◀️')
        await self.message.add_reaction('▶️')

        def check(reaction, user):
            return user == self.ctx.author and str(reaction.emoji) in ['◀️', '▶️'] and reaction.message.id == self.message.id

        while True:
            try:
                reaction, user = await bot.wait_for('reaction_add', timeout=60.0, check=check)
            except asyncio.TimeoutError:
                break
            else:
                await self.message.remove_reaction(reaction, user)
                if str(reaction.emoji) == '▶️' and self.current_page < (len(self.challenges) - 1) // 10:
                    self.current_page += 1
                elif str(reaction.emoji) == '◀️' and self.current_page > 0:
                    self.current_page -= 1

                await self.message.edit(embed=self.make_embed())

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

@bot.command(name='progress', help='Show the progress of a user or a group of users: !progress [user1] [user2] ...')
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

    await ctx.send(embed=embed)

@bot.command(name='remaining', help='Show the remaining challenges for a user: !remaining [user]')
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
