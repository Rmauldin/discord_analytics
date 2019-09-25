import discord
import logging
import sqlite3
import numpy as np
import matplotlib.pyplot as plt
import time, datetime
import re, os


# Logging and client setup
client = discord.Client()
logger = logging.getLogger('discord')
logger.setLevel(logging.DEBUG)
handler = logging.FileHandler(filename='discord.log', encoding='utf-8', mode='w')
handler.setFormatter(logging.Formatter('%(asctime)s:%(levelname)s:%(name)s: %(message)s'))
logger.addHandler(handler)

setattr(client, 'reactive', False)
reactive = False

# Database setup
setattr(client, 'db_conn', sqlite3.connect('analytics.db'))
setattr(client, 'db_cur', client.db_conn.cursor())

@client.event
async def on_ready():
	client.db_cur.execute("CREATE TABLE IF NOT EXISTS emoji(eid INTEGER PRIMARY KEY, name TEXT, bytes VARBINARY);")
	client.db_cur.execute("CREATE TABLE IF NOT EXISTS user(uid INTEGER PRIMARY KEY, name TEXT, display_name TEXT);")
	client.db_cur.execute("CREATE TABLE IF NOT EXISTS emoji_usage(uid INTEGER, eid INTEGER, date_used TIMESTAMP, \
																  FOREIGN KEY(eid) REFERENCES emoji(eid), \
																  FOREIGN KEY(uid) REFERENCES user(uid) );")
	try:
		client.db_conn.commit()
	except:
		client.db_conn.rollback()
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
	# TODO charts won't come out consistent
	# grab the most or least used custom emojis
	# if top=True, most used. Else least used
	if(top):
		client.db_cur.execute('SELECT emoji.name, COUNT(emoji_usage.eid) AS cnt FROM emoji LEFT JOIN emoji_usage ON emoji_usage.eid = emoji.eid \
		            GROUP BY emoji_usage.eid ORDER BY cnt DESC LIMIT 10')
	else:
		client.db_cur.execute('SELECT emoji.name, COUNT(emoji_usage.eid) AS cnt FROM emoji LEFT JOIN emoji_usage ON emoji_usage.eid = emoji.eid \
		            GROUP BY emoji_usage.eid ORDER BY cnt ASC LIMIT 10')
	emoji = client.db_cur.fetchall()
	emoji.sort(key=lambda x: x[1], reverse=not top)
	print(emoji)
	n = len(emoji)
	labels = [x[0] for x in emoji]
	values = [int(x[1]) for x in emoji]

	plt.barh(range(n), values, tick_label=labels, align='center', color='green')
	if(top):
		plt.title("Top Used Emojis")
	else:
		plt.title("Least Used Emojis")
	plt.ylabel("Emoji")
	plt.xlabel("Times used")
	plt.gcf().subplots_adjust(bottom=0.2)

	plt.savefig('stats.png', bbox_inches='tight', format='png')
	await message.channel.send(file=discord.File('stats.png'))
	os.remove('stats.png')


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

	command = message.content.split()[1]

	if(command == 'react'.lower()):
		client.reactive = True
		await message.channel.send("I'm now Reactive")
	elif(command == 'unreact'.lower()):
		client.reactive = False
		await message.channel.send("I'm now Unreactive")
	elif(command == 'top'.lower() or command == 'top10'.lower()):
		await client.post_stats(message, top=True)
	elif(command == 'bottom'.lower()):
		await client.post_stats(message, top=False)
	elif(command == 'help'.lower()):
		await message.channel.send('Commands:\nreact - Makes me reactive.\nunreact - Makes me unreactive.\ntop - Lists top 10 used emojis.\nbottom - Lists least 10 used emojis.\n')
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

client.run('NjE5NjYyNjgzNTc4MzAyNDk5.XXMazQ.n49orpmTWGO6SEaSaV9vwCshSx8')
