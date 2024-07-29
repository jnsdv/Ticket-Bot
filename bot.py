import discord
import json
from discord import *
from discord.ext import commands, tasks
from system import System
from commands import Command

with open("config.json", mode="r") as config_file:
    config = json.load(config_file)

BOT_TOKEN = config["token"]
GUILD_ID = config["guild_id"]
CATEGORY = config["category"]

bot = commands.Bot(intents=discord.Intents.all())


@bot.event
async def on_ready():
    print(f"Bot Started > {bot.user.name}")
    richpresence.start()


@tasks.loop(minutes=1)
async def richpresence():
    guild = bot.get_guild(GUILD_ID)
    category = discord.utils.get(guild.categories, id=int(CATEGORY))
    await bot.change_presence(
        activity=discord.Activity(
            type=discord.ActivityType.watching,
            name=f"Tickets | {len(category.channels)}",
        )
    )


bot.add_cog(System(bot))
bot.add_cog(Command(bot))
bot.run(BOT_TOKEN)
