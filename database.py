import sqlite3

# Connect to the SQLite database
conn = sqlite3.connect('challenges.db')

# Create a cursor object
c = conn.cursor()

# Create table for challenges
c.execute('''
    CREATE TABLE challenges (
        challenge_id INTEGER PRIMARY KEY,
        challenge_name TEXT NOT NULL,
        points INTEGER NOT NULL
    )
''')

# Create table for users' progress
c.execute('''
    CREATE TABLE user_progress (
        user_id TEXT NOT NULL,
        challenge_id INTEGER NOT NULL,
        is_completed BOOLEAN NOT NULL,
        FOREIGN KEY(challenge_id) REFERENCES challenges(challenge_id)
    )
''')

# Commit the changes and close the connection
conn.commit()
conn.close()
