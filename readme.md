# Analytics: A Bot for Discord
## Description
A discord bot that tracks chat analytics, such as emoji usage, and provides information via chat commands or a database file.
Built with <a href="https://discordpy.readthedocs.io/en/latest/index.html">discord.py</a>

## Features
- Logs and tracks uploaded emoji usage in database
- Can supplement reacts on messages
- Tracks user emoji usage

## Installation
Setup the environment with requirements.txt. Alter bot_info.json with your specific token for your account and then run analysis.py.

## Usage
	/analytics help

## List of commands:
	/analytics help - Lists supported commands.
	/analytics react - Makes me reactive. Reacts to existing reactions.
	/analytics unreact - Makes me unreactive. Stops reacts to existing reactions.
	/analytics top - Lists top 10 used emojis with a chart.
	/analytics bottom - Lists least 10 used emojis with a chart.
	/analytics users - Lists top 10 users who use the most emojis with a chart.
	/analytics reset - Resets the database. (Admin only)

## Notes
	- This bot requires self-hosting in order to store the database.
