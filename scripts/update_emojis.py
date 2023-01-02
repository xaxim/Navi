# update_emojis.py
"""Get emojis from dev servers and update emojis.py"""

import os
import re
import sys
import discord
from discord.ext import commands

from dotenv import load_dotenv


ENV_VARIABLE_MISSING = (
    'Required setting {var} in the .env file is missing. Please check your default.env file and update your .env file '
    'accordingly.'
)

# Load .env variables
load_dotenv()

NAVI_ROOT_DIR = os.path.abspath(f'{os.path.dirname(__file__)}/..')
ORIGINAL_EMOJI_FILE = f'{NAVI_ROOT_DIR}/resources/emojis.py'

TOKEN = os.getenv('DISCORD_TOKEN')
if TOKEN is None:
    print(ENV_VARIABLE_MISSING.format(var='DISCORD_TOKEN'))
    sys.exit()

DEV_GUILDS = os.getenv('DEV_GUILDS')
if DEV_GUILDS is None:
    print(ENV_VARIABLE_MISSING.format(var='DEV_GUILDS'))
    sys.exit()
if DEV_GUILDS == '':
    print('Variable DEV_GUILDS in the .env file is required. Please set at least one dev guild.')
    sys.exit()
else:
    DEV_GUILDS = DEV_GUILDS.split(',')
    try:
        DEV_GUILDS = [int(guild_id.strip()) for guild_id in DEV_GUILDS]
    except:
        print('At least one id in the .env variable DEV_GUILDS is not a number.')
        sys.exit()

rx = r'^<a?:\w+:'

f1 = open(ORIGINAL_EMOJI_FILE, 'r+')

oemojis = f1.readlines()

f1.seek(0)
f1.truncate()



intents = discord.Intents.none()
intents.guilds = True   # for on_guild_join() and all guild objects

bot = commands.Bot(intents)


@bot.event
async def on_ready() -> None:
    """Fires when bot has finished starting"""
    startup_info = f'{bot.user.name} has connected to Discord!'
    print(startup_info)
    await bot.change_presence(activity=discord.Activity(type=discord.ActivityType.watching, name='those emojis!'))

    nemojis = []
    for guildId in DEV_GUILDS:
        nemojis += bot.get_guild(guildId).emojis

    for oe in oemojis:
        if(oe.__contains__('<')):
            for ne in nemojis:
                oes = oe.split('=')
                if(re.match(rx, oes[1].replace('\'', '').strip()).group() == re.match(rx, str(ne)).group()):
                    f1.write(f'{oes[0]} = \'{str(ne)}\'\n')
        else:
            f1.write(oe)

    f1.close()
    print('Done!')
    await bot.close()
    exit(0)


bot.run(TOKEN)