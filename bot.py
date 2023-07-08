import discord
import sqlite3
import random
import os 
import math
import asyncio
from dotenv import load_dotenv
from discord.ext import commands

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
    print(f'We have logged in as {bot.user}')
    bot.intents.members = True

@bot.command(name='help', help='Display a list of all commands and what they do.')
async def help(ctx):
    help_embed = discord.Embed(title="Bot Commands", color=discord.Color.blue())
    help_embed.add_field(name="!add_challenge [challenge] [points]", value="Adds a challenge if it doesn't already exist. Example: !add_challenge \"challenge name\" 10")
    help_embed.add_field(name="!complete [user] [challenge]", value="Mark a challenge as completed for a user. Example: !complete @user \"challenge name\"")
    help_embed.add_field(name="!leaderboard", value="Show the leaderboard.")
    help_embed.add_field(name="!remaining [user]", value="Show the remaining challenges for a user.")
    help_embed.add_field(name="!all_challenges", value="List all challenges. Displays 10 challenges per page.")
    help_embed.add_field(name="!user_stats [user]", value="Display the completed challenges and points of a user.")
    help_embed.add_field(name="!random_challenge [user]", value="Get a random challenge for a user.")
    help_embed.add_field(name="!help", value="Display this message.")
    await ctx.send(embed=help_embed)

@bot.command(name='add_challenge', help='Adds a challenge: !add_challenge challenge points')
async def add_challenge(ctx, challenge: str, points: int):
    conn = sqlite3.connect('challenges.db')
    c = conn.cursor()
    c.execute("SELECT * FROM challenges WHERE LOWER(challenge_name) = ?", (challenge.lower(),))
    if c.fetchone() is None:
        c.execute("INSERT INTO challenges (challenge_name, points) VALUES (?, ?)", (challenge, points))
        await ctx.send(f'Challenge {challenge} for {points} points added.')
    else:
        await ctx.send('This challenge already exists.')
    conn.commit()
    conn.close()

@bot.command(name='all_challenges', help='Lists all challenges.')
async def all_challenges(ctx):
    conn = sqlite3.connect('challenges.db')
    c = conn.cursor()
    c.execute("SELECT challenge_name, points FROM challenges ORDER BY points DESC")
    all_challenges = c.fetchall()
    conn.close()

    paginator = ChallengePaginator(ctx, all_challenges, "All Challenges")
    await paginator.start()

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

    conn.close()

    # Create embed
    embed = discord.Embed(title=f"{user.name}'s Stats", color=discord.Color.blue())
    embed.add_field(name="__Total Points__", value=f"{total_points or 0}", inline=True)
    embed.add_field(name="__Completed Challenges__", value=f"{len(completed_challenges) or 0}", inline=True)
    
    if completed_challenges:
        challenges_list = '\n'.join([f"{name} ({points} points)" for name, points in completed_challenges])
        embed.add_field(name="__Challenge List__", value=f"{challenges_list}", inline=False)
    else:
        embed.add_field(name="__Challenge List__", value="No completed challenges", inline=False)

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
        await ctx.send(f'A random challenge for {user.name} is "{random_challenge[0]}" for **{random_challenge[1]} points**.')
    else:
        await ctx.send(f'{user.name} has completed all challenges.')
    conn.close()

@bot.command(name='complete', help='Mark a challenge as completed for a user: !complete user "challenge name"')
async def complete(ctx, user: discord.User, challenge: str):
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
    c.execute("UPDATE user_progress SET is_completed = ? WHERE user_id = ? AND challenge_id = ?", (True, user.id, challenge_id))
    c.execute("""
        SELECT SUM(challenges.points)
        FROM user_progress
        INNER JOIN challenges ON user_progress.challenge_id = challenges.challenge_id
        WHERE user_progress.user_id = ? AND user_progress.is_completed = ?
    """, (user.id, True))
    total_points = c.fetchone()[0]
    conn.commit()
    conn.close()
    await ctx.send(f'{user.name} has completed the "{challenge}" challenge and now has **{total_points or 0} points**.')

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
    for i, (user_id, total_points) in enumerate(results, start=1):
        user = await bot.fetch_user(user_id)
        leaderboard_embed.add_field(name=f"{i}. {user.name}", value=f"{total_points or 0} points", inline=False)
    if len(results) == 0:
        leaderboard_embed.description = 'The leaderboard is empty.'
    await ctx.send(embed=leaderboard_embed)

class ChallengePaginator:

    def __init__(self, ctx, challenges, title):
        self.ctx = ctx
        self.challenges = challenges
        self.current_page = 0
        self.title = title

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
            challenge_name, points = self.challenges[i]
            embed.description += f'{i+1}. **{challenge_name}** for `{points} points`\n' # type: ignore

        total_pages = (len(self.challenges) + 9) // 10
        embed.set_footer(text=f"Page {self.current_page + 1} of {total_pages}")

        return embed


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
    paginator = ChallengePaginator(ctx, results, f'Remaining challenges for {user.name}')
    await paginator.start()



bot.run(TOKEN) # type: ignore
