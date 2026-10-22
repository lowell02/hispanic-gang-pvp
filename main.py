
import os
import discord
from discord.ext import commands

intents = discord.Intents.default()

bot = commands.Bot(command_prefix="!", intents=intents)

@bot.event
async def on_ready():
    print(f"⚔️ HISPANIC GANG conectado como {bot.user}")

@bot.tree.command(name="ping", description="Comprueba si el bot está funcionando")
async def ping(interaction: discord.Interaction):
    await interaction.response.send_message("🏓 ¡HISPANIC GANG está funcionando!")

@bot.event
async def setup_hook():
    await bot.tree.sync()

token = os.getenv("DISCORD_TOKEN")

if not token:
    raise RuntimeError("Falta configurar DISCORD_TOKEN")

bot.run(token)
