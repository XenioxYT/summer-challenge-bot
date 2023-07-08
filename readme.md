# Discord Challenge Bot

This bot is designed to manage and track challenges for users in a Discord server. It uses SQLite for data storage.

## Commands

The bot provides the following commands:

1. `!add_challenge [challenge] [points]`: Adds a new challenge if it doesn't already exist. You can add multiple challenges at once by separating them with commas. Example: `!add_challenge "challenge name" 10`. Another example: `!add_challenge "challenge1", "challenge2", "challenge3" 10`.

2. `!all_challenges`: Lists all challenges in the database.

3. `!user_stats [user]`: Retrieves statistics for a user.

4. `!random_challenge [user]`: Selects a random challenge for a user.

5. `!complete [challenge name]`: Marks a challenge as completed for a user.

6. `!leaderboard`: Displays the leaderboard of all users.

7. `!progress [user1] [user2] ...`: Shows the progress of a user or a group of users.

8. `!remaining [user]`: Shows the remaining challenges for a user.

9. `!search [keyword]`: Search for challenges.

10. `!delete_challenge [challenge]`: Delete a challenge. Example: `!delete_challenge [challenge name]`.

11. `!help`: Display the list of commands.

## Installation

To use this bot, you need to have Python installed. If you don't have Python installed, you can download it from the [official website](https://www.python.org/downloads/).

1. Clone this repository to your local machine.

2. Install the required dependencies. The bot requires the following libraries, which you can install with pip:

```
pip install discord.py
pip install python-dotenv
pip install fuzzywuzzy
pip install python-Levenshtein
pip install discord-py-slash-command # not really needed, mainly used for testing purposes. If any errors occur without this, be sure to install it.
```

3. Create a new bot on the [Discord developer portal](https://discord.com/developers/applications) and get your bot token.

4. Replace `TOKEN` in the `bot.run(TOKEN)` line at the end of the bot.py file with your bot token.

5. Run the bot.py file:

```
python bot.py
```

The bot should now be running and ready to join a server!

## Usage

To use the bot commands, type the command name preceded by an exclamation mark in a text channel where the bot has permission to read and send messages. For example, to add a new challenge:

```
!add_challenge "Challenge Name" 50
```

## Contributing

Contributions are welcome! Please feel free to submit a pull request.

## License

This project is licensed under the terms of the MIT license.
