import discord
import logging
import sqlite3
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

if(not info['database_folder'].endswith('/')):
	info['database_folder'] = info['database_folder'] + "/"

setattr(client, 'reactive', False)

# Database setup
setattr(client, 'db_conn', dict() )
setattr(client, 'db_cur', dict() )

@client.event
async def create_database(guild):
	if not os.path.exists(info['database_folder']):
		os.makedirs(info['database_folder'])
	guild_id = guild.id
	client.db_conn[guild_id] = sqlite3.connect("{}{}.db".format(info['database_folder'], guild_id))
	client.db_cur[guild_id] = client.db_conn[guild_id].cursor()

	client.db_cur[guild_id].execute("CREATE TABLE IF NOT EXISTS emoji(eid INTEGER PRIMARY KEY, name TEXT, animated INTEGER);")
	client.db_cur[guild_id].execute("CREATE TABLE IF NOT EXISTS user(uid INTEGER PRIMARY KEY, name TEXT, display_name TEXT);")
	client.db_cur[guild_id].execute("CREATE TABLE IF NOT EXISTS emoji_usage(uid INTEGER, eid INTEGER, date_used TIMESTAMP, \
																  FOREIGN KEY(eid) REFERENCES emoji(eid), \
																  FOREIGN KEY(uid) REFERENCES user(uid) );")

	await client.add_users(guild)
	await client.add_emojis(guild)

	try:
		client.db_conn[guild_id].commit()
	except:
		client.db_conn[guild_id].rollback()

@client.event
async def create_databases():
	for guild in client.guilds:
		await client.create_database(guild)

@client.event
async def on_member_join(member):
	await client.log_member(member)

@client.event
async def add_users(guild):
	guild_id = guild.id
	for member in guild.members:
		if(not member.bot):
			await client.log_member(member)

@client.event
async def log_member(member):
	guild_id = member.guild.id
	client.db_cur[guild_id].execute("INSERT OR IGNORE INTO user (uid, name, display_name) VALUES (?, ?, ?)", \
										(member.id, member.name, member.display_name))
	try:
		client.db_conn[guild_id].commit()
	except:
		client.db_conn[guild_id].rollback()

@client.event
async def add_emojis(guild):
	guild_id = guild.id
	for emoji in guild.emojis:
		client.db_cur[guild_id].execute("INSERT OR IGNORE INTO emoji (eid, name, animated) VALUES (?, ?, ?)", \
										(emoji.id, emoji.name, 1 if emoji.animated else 0))

@client.event
async def on_ready():
	await client.user.edit(username=info['bot_name'])
	await client.create_databases()
	print("Logged in as {0.user}".format(client))

@client.event
async def log_emoji_usage(emoji, user):
	timestamp = str(datetime.datetime.fromtimestamp(time.time()).strftime('%Y-%m-%d %H:%M:%S'))
	guild_id = user.guild.id

	# client.db_cur[guild_id].execute("INSERT OR IGNORE INTO emoji (eid, name, animated) VALUES (?, ?, ?)", \
	# 						(emoji.id, emoji.name, 1 if emoji.animated else 0))
	# client.db_cur.execute("INSERT OR IGNORE INTO user (uid, name, display_name) VALUES (?, ?, ?)", \
	# 						(user.id, user.name, user.display_name))
	client.db_cur[guild_id].execute("INSERT INTO emoji_usage(uid, eid, date_used) VALUES (?, ?, ?)",\
							(user.id, emoji.id, timestamp))
	try:
		client.db_conn[guild_id].commit()
	except:
		client.db_conn[guild_id].rollback()

	print("{}: Logged :{}:".format(timestamp, emoji.name))

@client.event
async def log_emoji_usages(emojis, user):
	for emoji in emojis:
		await client.log_emoji_usage(emoji, user)

	# if(len(possible_emojis) == 0):
	# 	return

	# guild_emojis = {x.name : x for x in message.guild.emojis}

	# emojis = [guild_emojis[x] for x in guild_emojis.keys()&possible_emojis]

	# for e in emojis:
	# 	await log_emoji_usage(e, message.author)

@client.event
async def on_guild_emojis_update(guild, before, after):
	guild_id = guild.id
	before_set = set(before)
	after_set = set(after)
	removed = before_set - after_set
	# update emojies
	for emoji in after:
		client.db_cur[guild_id].execute("UPDATE OR IGNORE emoji SET name=? WHERE eid=?", (emoji.name, emoji.id))
		if emoji not in before_set:
			print("Added " + emoji.name) 

	for emoji in removed:
		client.db_cur[guild_id].execute("DELETE FROM emoji WHERE eid=?", (emoji.id,))
		client.db_cur[guild_id].execute("DELETE FROM emoji_usage WHERE eid=?", (emoji.id,))
		print("Removed " + emoji.name)

	try:
		client.db_conn[guild_id].commit()
	except:
		client.db_conn[guild_id].rollback()

@client.event
async def post_stats(message, top):
	# grab the most or least used custom emojis
	# if top=True, most used. Else least used
	guild_id = message.guild.id

	if(top):
		client.db_cur[guild_id].execute('SELECT emoji.name, COUNT(emoji_usage.eid) AS cnt FROM emoji LEFT JOIN emoji_usage ON emoji_usage.eid = emoji.eid \
		            GROUP BY emoji_usage.eid ORDER BY cnt DESC LIMIT 10')
	else:
		client.db_cur[guild_id].execute('SELECT emoji.name, COUNT(emoji_usage.eid) AS cnt FROM emoji LEFT JOIN emoji_usage ON emoji_usage.eid = emoji.eid \
		            GROUP BY emoji_usage.eid ORDER BY cnt ASC LIMIT 10')

	emoji = client.db_cur[guild_id].fetchall()

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
	guild_id = message.guild.id
	client.db_cur[guild_id].execute('SELECT user.name, COUNT(emoji_usage.uid) AS cnt FROM user LEFT JOIN emoji_usage ON emoji_usage.uid = user.uid \
            GROUP BY emoji_usage.uid ORDER BY cnt DESC LIMIT 10')

	users = client.db_cur[guild_id].fetchall()

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
async def reset_database(message):
	guild_id = message.guild.id
	print("Resetting database.")
	client.db_conn[guild_id].close()
	print("Database connection closed.")
	try:
		os.remove("{}{}.db.bak".format(info['database_folder'], guild_id))
	except OSError as e:
		pass
	try:
		os.rename("{}{}.db".format(guild_id), "{}.db.bak".format(info['database_folder'], guild_id))
	except PermissionError as e:
		await message.channel.send("Cannot reset database; currently in use by another process.")

	await client.create_database(message.guild)

@client.event
async def reset_table(message):
	if(message.channel.permissions_for(message.author).administrator):
		await client.reset_database(message)
		await message.channel.send("Database reset.")
	else:
		await message.channel.send("Only admins can reset the database.")

@client.event
async def extract_custom_emojis(message):
	emojis_raw = re.findall(r'<a?:(\S*):([0-9]*)>', message.content)

	if(len(emojis_raw) == 0):
		return []

	guild_emojis = {x.id : x for x in message.guild.emojis}

	emojis = []

	for emoji in emojis_raw:
		if(int(emoji[1]) in guild_emojis.keys()):
			emojis.append( guild_emojis[int(emoji[1])] )

	return emojis

@client.event
async def on_member_update(before, after):
	guild_id = after.guild.id
	client.db_cur[guild_id].execute("UPDATE user SET display_name=? WHERE uid=?", (after.display_name, after.id))

	try:
		client.db_conn[guild_id].commit()
	except:
		client.db_conn[guild_id].rollback()

@client.event
async def on_guild_join(guild):
	await client.create_database(guild)

@client.event
async def display_help_menu(message):
	await message.channel.send('Hi! I keep track of your server custom emoji usage.\n\
	Commands: /analytics \n\
	react - Makes me reactive.\n\
	unreact - Makes me unreactive.\n\
	top - Lists top 10 used emojis.\n\
	bottom - Lists least 10 used emojis.\n\
	users - Lists top 10 users who use the most emojis.\n\
	adminhelp - List admin commands.\n\
	')

@client.event
async def display_admin_menu(message):
	# TODO: Add command to get db file?
	await message.channel.send('Hi! I keep track of your server custom emoji usage.\n\
	Commands: /analytics \n\
	reset - Resets the database.\n\
	')

@client.event
async def on_message(message):
	if(message.author.bot):
		return

	# Logging...
	emojis = await client.extract_custom_emojis(message)

	await client.log_emoji_usages(emojis, message.author)

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
		await client.display_help_menu(message)
	elif(command == 'adminhelp'):
		await client.display_admin_menu(message)
	else:
		await message.channel.send("Unrecognized command. Try \"/analytics help\"")

@client.event
async def on_reaction_add(reaction, user):
	if(user.bot):
		return

	if(reaction.custom_emoji):
		await log_emoji_usage(reaction.emoji, user)

	if(client.reactive):
		await reaction.message.add_reaction(reaction.emoji)

@client.event
async def on_reaction_remove(reaction, user):
	if(user.bot):
		return
	if(reaction.count == 1):
		await reaction.message.remove_reaction(reaction, client.user)

@client.event
async def on_disconnect():
	for conn in client.db_conn:
		conn.close()
	print("Database connections closed.")

client.run(info['token'])
