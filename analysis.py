import discord
import logging
import sqlite3
import numpy as np
import matplotlib.pyplot as plt
import time, datetime
import re, os
import json

# Logging and client setup
client = discord.Client(activity=discord.Game('/analytics help'))
logger = logging.getLogger('discord')
logger.setLevel(logging.DEBUG)
handler = logging.FileHandler(filename='discord.log', encoding='utf-8', mode='w')
handler.setFormatter(logging.Formatter('%(asctime)s:%(levelname)s:%(name)s: %(message)s'))
logger.addHandler(handler)

# Setup info dict
with open('bot_info.json') as f:
	info = json.load(f)

setattr(client, 'reactive', False)
reactive = False

# Database setup
setattr(client, 'db_conn', sqlite3.connect(info['database_name']))
setattr(client, 'db_cur', client.db_conn.cursor())

@client.event
async def create_database():
	client.db_cur.execute("CREATE TABLE IF NOT EXISTS emoji(eid INTEGER PRIMARY KEY, name TEXT, bytes VARBINARY);")
	client.db_cur.execute("CREATE TABLE IF NOT EXISTS user(uid INTEGER PRIMARY KEY, name TEXT, display_name TEXT);")
	client.db_cur.execute("CREATE TABLE IF NOT EXISTS emoji_usage(uid INTEGER, eid INTEGER, date_used TIMESTAMP, \
																  FOREIGN KEY(eid) REFERENCES emoji(eid), \
																  FOREIGN KEY(uid) REFERENCES user(uid) );")
	try:
		client.db_conn.commit()
	except:
		client.db_conn.rollback()

@client.event
async def on_ready():
	await client.user.edit(username=info['bot_name'])
	await client.create_database()
	print("Logged in as {0.user}".format(client))


@client.event
async def log_emoji(emoji, user):
	timestamp = str(datetime.datetime.fromtimestamp(time.time()).strftime('%Y-%m-%d %H:%M:%S'))

	if(not emoji.animated):
		emoji_bytes = await emoji.url.read()
	else:
		emoji_bytes = None

	client.db_cur.execute("INSERT OR IGNORE INTO emoji (eid, name, bytes) VALUES (?, ?, ?)", \
							(emoji.id, emoji.name, emoji_bytes))
	client.db_cur.execute("INSERT OR IGNORE INTO user (uid, name, display_name) VALUES (?, ?, ?)", \
							(user.id, user.name, user.display_name))
	# client.db_cur.execute("UPDATE emoji_usage as E SET count=count + 1, date_used=? WHERE E.uid=? AND E.eid=? AND \
	# 						EXISTS(SELECT 1 FROM emoji_usage as EM WHERE EM.uid=E.uid AND EM.eid=E.eid)", \
	# 						(timestamp, user.id, emoji.id))
	client.db_cur.execute("INSERT OR IGNORE INTO emoji_usage(uid, eid, date_used) VALUES (?, ?, ?)",\
							(user.id, emoji.id, timestamp))
	try:
		client.db_conn.commit()
	except:
		client.db_conn.rollback()

	print("Logged :" + emoji.name + ":")

@client.event
async def log_emojis(message, possible_emojis):

	if(len(possible_emojis) == 0):
		return

	guild_emojis = {x.name : x for x in message.guild.emojis}

	emojis = [guild_emojis[x] for x in guild_emojis.keys()&possible_emojis]

	for e in emojis:
		await log_emoji(e, message.author)

@client.event
async def on_guild_emojis_update(guild, before, after):
	before_set = set(before)
	after_set = set(after)
	removed = before_set - after_set
	# update emojies
	for emoji in after:
		client.db_cur.execute("UPDATE OR IGNORE emoji SET name=? WHERE eid=?", (emoji.name, emoji.id))
		if emoji not in before_set:
			print("Added " + emoji.name) 

	for emoji in removed:
		client.db_cur.execute("DELETE FROM emoji WHERE eid=?", (emoji.id,))
		client.db_cur.execute("DELETE FROM emoji_usage WHERE eid=?", (emoji.id,))
		print("Removed " + emoji.name)

	try:
		client.db_conn.commit()
	except:
		client.db_conn.rollback()

@client.event
async def post_stats(message, top):
	# grab the most or least used custom emojis
	# if top=True, most used. Else least used
	if(top):
		client.db_cur.execute('SELECT emoji.name, COUNT(emoji_usage.eid) AS cnt FROM emoji LEFT JOIN emoji_usage ON emoji_usage.eid = emoji.eid \
		            GROUP BY emoji_usage.eid ORDER BY cnt DESC LIMIT 10')
	else:
		client.db_cur.execute('SELECT emoji.name, COUNT(emoji_usage.eid) AS cnt FROM emoji LEFT JOIN emoji_usage ON emoji_usage.eid = emoji.eid \
		            GROUP BY emoji_usage.eid ORDER BY cnt ASC LIMIT 10')

	emoji = client.db_cur.fetchall()

	n = len(emoji)
	labels = [x[0] for x in emoji]
	values = [int(x[1]) for x in emoji]

	plt.barh(range(n), values, tick_label=labels, color='green')
	if(top):
		plt.title("Top Used Emojis")
	else:
		plt.title("Least Used Emojis")
	plt.ylabel("Emoji")
	plt.xlabel("Times used")
	plt.gcf().subplots_adjust(bottom=0.2)
	plt.gca().invert_yaxis()
	plt.savefig('stats.png', bbox_inches='tight', format='png')
	await message.channel.send(file=discord.File('stats.png'))
	plt.clf()
	os.remove('stats.png')

@client.event
async def user_stats(message):
	client.db_cur.execute('SELECT user.name, COUNT(emoji_usage.uid) AS cnt FROM user LEFT JOIN emoji_usage ON emoji_usage.uid = user.uid \
            GROUP BY emoji_usage.uid ORDER BY cnt DESC LIMIT 10')

	users = client.db_cur.fetchall()

	n = len(users)
	labels = [x[0] for x in users]
	values = [int(x[1]) for x in users]

	plt.barh(range(n), values, tick_label=labels, color='blue')
	plt.title("Top Users Who Use Emojis")
	plt.ylabel("User")
	plt.xlabel("Times used")
	plt.gcf().subplots_adjust(bottom=0.2)
	plt.gca().invert_yaxis()
	plt.savefig('users.png', bbox_inches='tight', format='png')
	await message.channel.send(file=discord.File('users.png'))
	plt.clf()
	os.remove('users.png')

@client.event
async def reset_database():
	print("Resetting database.")
	client.db_conn.close()
	print("Database connection closed.")
	try:
		os.remove("{}.bak".format(info['database_name']))
	except OSError as e:
		pass
	try:
		os.rename(info['database_name'], "{}.bak".format(info['database_name']))
	except PermissionError as e:
		await message.channel.send("Cannot reset database; currently in use by another process.")


	client.db_conn = sqlite3.connect(info['database_name'])
	client.db_cur = client.db_conn.cursor()
	await client.create_database()

@client.event
async def reset_table(message):
	if(message.channel.permissions_for(message.author).administrator):
		await client.reset_database()
		await message.channel.send("Database reset.")
	else:
		await message.channel.send("Only admins can reset the database.")

@client.event
async def on_message(message):
	if(message.author.bot):
		return

	# Logging...

	possible_emojis = set( re.findall(r'(?<=<:)([^:\s]+)(?=:(?:\d))', message.content)  )
	possible_animated_emojis = set( re.findall(r'(?<=<a:)([^:\s]+)(?=:(?:\d))', message.content)  )
	# print("possible_emojis: " + str(possible_emojis))
	if(len(possible_emojis) != 0):
		await client.log_emojis(message, possible_emojis)

	if(len(possible_emojis) != 0):
		await client.log_emojis(message, possible_animated_emojis)

	if(not message.content.startswith("/analytics ")):
		return

	# If a command...

	command = message.content.split()[1].lower()

	if(command == 'react'):
		client.reactive = True
		await message.channel.send("I'm now Reactive")
	elif(command == 'unreact'):
		client.reactive = False
		await message.channel.send("I'm now Unreactive")
	elif(command == 'top'):
		await client.post_stats(message, top=True)
	elif(command == 'bottom'):
		await client.post_stats(message, top=False)
	elif(command == 'users'):
		await client.user_stats(message)
	elif(command == 'reset'):
		await client.reset_table(message)
	elif(command == 'help'):
		await message.channel.send('Hi! I keep track of your server custom emoji usage.\nCommands: /analytics \nreact - Makes me reactive.\nunreact - Makes me unreactive.\ntop - Lists top 10 used emojis.\nbottom - Lists least 10 used emojis.\nusers - Lists top 10 users who use the most emojis.\nreset - Resets the database. (Admin only)\n')
	else:
		await message.channel.send("Unrecognized command. Try \"/analytics help\"")

@client.event
async def on_reaction_add(reaction, user):
	if(user.bot):
		return
	if(client.reactive):
		await reaction.message.add_reaction(reaction.emoji)

	if(reaction.custom_emoji):
		await log_emoji(reaction.emoji, user)

@client.event
async def on_reaction_remove(reaction, user):
	if(user.bot):
		return
	if(reaction.count == 1):
		await reaction.message.remove_reaction(reaction, client.user)

@client.event
async def on_disconnect():
	client.db_conn.close()
	print("Database connection closed.")

client.run(info['token'])
