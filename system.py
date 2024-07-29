import discord
import asyncio
import pytz
import json
import sqlite3
from datetime import datetime
import chat_exporter
import io
from discord.ext import commands

with open("config.json", mode="r") as config_file:
    config = json.load(config_file)

GUILD_ID = config["guild_id"]
TICKET_CHANNEL = config["ticket_channel"]
CATEGORY_ID = config["category"]
TEAM_ROLE = config["team_role"]
LOG_CHANNEL = config["log_channel"]
TIMEZONE = config["timezone"]
EMBED_TITLE = config["embed_title"]
EMBED_DESCRIPTION = config["embed_description"]

conn = sqlite3.connect("database.db")
cur = conn.cursor()

cur.execute("""CREATE TABLE IF NOT EXISTS ticket 
           (id INTEGER PRIMARY KEY AUTOINCREMENT, discord_name TEXT, discord_id INTEGER, ticket_channel TEXT, ticket_created TIMESTAMP)""")
conn.commit()


class System(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_ready(self):
        print(f"Loaded: System ✅")
        self.bot.add_view(View(bot=self.bot))
        self.bot.add_view(CloseButton(bot=self.bot))
        self.bot.add_view(TicketOptions(bot=self.bot))

    @commands.Cog.listener()
    async def on_bot_shutdown():
        cur.close()
        conn.close()


class View(discord.ui.View):
    def __init__(self, bot):
        self.bot = bot
        super().__init__(timeout=None)

    @discord.ui.select(
        custom_id="support",
        placeholder="Choose a Ticket option",
        options=[
            discord.SelectOption(
                label="Support1",
                description="You will get help here!",
                emoji="❓",
                value="support1",
            ),
            discord.SelectOption(
                label="Support2",
                description="Ask questions here!",
                emoji="📛",
                value="support2",
            ),
        ],
    )
    async def callback(self, select, interaction):
        await interaction.response.defer()
        timezone = pytz.timezone(TIMEZONE)
        creation_date = datetime.now(timezone).strftime("%Y-%m-%d %H:%M:%S")
        user_name = interaction.user.name
        user_id = interaction.user.id

        cur.execute("SELECT discord_id FROM ticket WHERE discord_id=?", (user_id,))
        existing_ticket = cur.fetchone()

        if existing_ticket is None:

            ticket_name = "ticket"
            welcome = "Welcome to your ticket"

            if interaction.channel.id == TICKET_CHANNEL:
                
                if "support1" in interaction.data["values"]:
                    welcome = "Welcome to your ticket in support category 1"

                if "support2" in interaction.data["values"]:
                    welcome = "You chose support category 2"

                guild = self.bot.get_guild(GUILD_ID)

                cur.execute(
                    "INSERT INTO ticket (discord_name, discord_id, ticket_created) VALUES (?, ?, ?)",
                    (user_name, user_id, creation_date),
                )
                conn.commit()
                await asyncio.sleep(1)
                cur.execute("SELECT id FROM ticket WHERE discord_id=?", (user_id,))
                ticket_number = cur.fetchone()[0]

                category = self.bot.get_channel(CATEGORY_ID)
                ticket_channel = await guild.create_text_channel(
                    f"{ticket_name}-{ticket_number}",
                    category=category,
                    topic=f"{interaction.user.id}",
                )

                await ticket_channel.set_permissions(
                    guild.get_role(TEAM_ROLE),
                    send_messages=True,
                    read_messages=True,
                    add_reactions=False,
                    embed_links=True,
                    attach_files=True,
                    read_message_history=True,
                    external_emojis=True,
                )
                await ticket_channel.set_permissions(
                    interaction.user,
                    send_messages=True,
                    read_messages=True,
                    add_reactions=False,
                    embed_links=True,
                    attach_files=True,
                    read_message_history=True,
                    external_emojis=True,
                )
                await ticket_channel.set_permissions(
                    guild.default_role,
                    send_messages=False,
                    read_messages=False,
                    view_channel=False,
                )
                embed = discord.Embed(
                    description=f"Welcome {interaction.user.mention},\n"
                    + welcome,
                    color=discord.colour.Color.blue(),
                )
                await ticket_channel.send(
                    embed=embed, view=CloseButton(bot=self.bot)
                )

                channel_id = ticket_channel.id
                cur.execute(
                    "UPDATE ticket SET ticket_channel = ? WHERE id = ?",
                    (channel_id, ticket_number),
                )
                conn.commit()

                embed = discord.Embed(
                    description=f"📬 Ticket was Created! --> {ticket_channel.mention}",
                    color=discord.colour.Color.green(),
                )
                await interaction.followup.send(embed=embed, ephemeral=True)
                await asyncio.sleep(1)
                embed = discord.Embed(
                    title=EMBED_TITLE,
                    description=EMBED_DESCRIPTION,
                    color=discord.colour.Color.blue(),
                )
                await interaction.message.edit(
                    embed=embed, view=View(bot=self.bot)
                )
                    
        else:
            embed = discord.Embed(
                title=f"You already have a ticket open!", color=0xFF0000
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
            await asyncio.sleep(1)
            embed = discord.Embed(
                title=EMBED_TITLE,
                description=EMBED_DESCRIPTION,
                color=discord.colour.Color.blue(),
            )
            await interaction.message.edit(embed=embed, view=View(bot=self.bot))


class CloseButton(discord.ui.View):
    def __init__(self, bot):
        self.bot = bot
        super().__init__(timeout=None)

    @discord.ui.button(
        label="Close Ticket 🎫", style=discord.ButtonStyle.blurple, custom_id="close"
    )
    async def close(self, button: discord.ui.Button, interaction: discord.Interaction):
        embed = discord.Embed(
            title="Close Ticket 🎫",
            description="Are you sure you want to close this Ticket?",
            color=discord.colour.Color.green(),
        )
        await interaction.response.send_message(
            embed=embed, view=TicketOptions(bot=self.bot)
        )
        await interaction.message.edit(view=self)


class TicketOptions(discord.ui.View):
    def __init__(self, bot):
        self.bot = bot
        super().__init__(timeout=None)

    @discord.ui.button(
        label="Close Ticket 🎫", style=discord.ButtonStyle.red, custom_id="delete"
    )
    async def delete_button(
        self, button: discord.ui.Button, interaction: discord.Interaction
    ):
        guild = self.bot.get_guild(GUILD_ID)
        channel = self.bot.get_channel(LOG_CHANNEL)
        ticket_id = interaction.channel.id

        cur.execute(
            "SELECT id, discord_id, ticket_created FROM ticket WHERE ticket_channel=?",
            (ticket_id,),
        )
        ticket_data = cur.fetchone()
        id, ticket_creator_id, ticket_created = ticket_data
        ticket_creator = guild.get_member(ticket_creator_id)

        ticket_created_unix = self.convert_to_unix_timestamp(ticket_created)
        timezone = pytz.timezone(TIMEZONE)
        ticket_closed = datetime.now(timezone).strftime("%Y-%m-%d %H:%M:%S")
        ticket_closed_unix = self.convert_to_unix_timestamp(ticket_closed)

        military_time: bool = True
        transcript = await chat_exporter.export(
            interaction.channel,
            limit=200,
            tz_info=TIMEZONE,
            military_time=military_time,
            bot=self.bot,
        )

        transcript_file = discord.File(
            io.BytesIO(transcript.encode()),
            filename=f"transcript-{interaction.channel.name}.html",
        )
        transcript_file2 = discord.File(
            io.BytesIO(transcript.encode()),
            filename=f"transcript-{interaction.channel.name}.html",
        )

        embed = discord.Embed(
            description=f"Ticket is closing in 5 seconds.", color=0xFF0000
        )
        transcript_info = discord.Embed(
            title=f"Ticket Closed | {interaction.channel.name}",
            color=discord.colour.Color.blue(),
        )
        transcript_info.add_field(name="ID", value=id, inline=True)
        transcript_info.add_field(
            name="Opened by", value=ticket_creator.mention, inline=True
        )
        transcript_info.add_field(
            name="Closed by", value=interaction.user.mention, inline=True
        )
        transcript_info.add_field(
            name="Ticket Created", value=f"<t:{ticket_created_unix}:f>", inline=True
        )
        transcript_info.add_field(
            name="Ticket Closed", value=f"<t:{ticket_closed_unix}:f>", inline=True
        )

        await interaction.response.send_message(embed=embed)
        try:
            await ticket_creator.send(embed=transcript_info, file=transcript_file)
        except:
            transcript_info.add_field(
                name="Error", value="Ticket Creator DM`s are disabled", inline=True
            )

        await channel.send(embed=transcript_info, file=transcript_file2)
        await asyncio.sleep(3)
        await interaction.channel.delete(reason="Ticket Closed")
        cur.execute("DELETE FROM ticket WHERE discord_id=?", (ticket_creator_id,))
        conn.commit()

    def convert_to_unix_timestamp(self, date_string):
        date_format = "%Y-%m-%d %H:%M:%S"
        dt_obj = datetime.strptime(date_string, date_format)
        berlin_tz = pytz.timezone("Europe/Berlin")
        dt_obj = berlin_tz.localize(dt_obj)
        dt_obj_utc = dt_obj.astimezone(pytz.utc)
        return int(dt_obj_utc.timestamp())
