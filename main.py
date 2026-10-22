import os
import asyncio
from datetime import datetime, timezone

import discord
from discord import app_commands
from discord.ext import commands, tasks
from supabase import create_client

COOLDOWN_SECONDS = 5 * 60 * 60
PANEL_UPDATE_SECONDS = 60
BURGUNDY = discord.Color.from_rgb(128, 0, 32)

TOKEN = os.environ.get('DISCORD_TOKEN')
SUPABASE_URL = os.environ.get('SUPABASE_URL')
SUPABASE_KEY = os.environ.get('SUPABASE_KEY')
if not all((TOKEN, SUPABASE_URL, SUPABASE_KEY)):
    raise RuntimeError('Configura DISCORD_TOKEN, SUPABASE_URL y SUPABASE_KEY en FadeHost.')

db = create_client(SUPABASE_URL, SUPABASE_KEY)
intents = discord.Intents.default()
bot = commands.Bot(command_prefix='!', intents=intents)


def now_unix():
    return int(datetime.now(timezone.utc).timestamp())


def member_rows(guild_id):
    return db.table('pvp_members').select('user_id,expires_at').eq('guild_id', str(guild_id)).order('user_id').execute().data or []


def make_embed(guild_id):
    rows = member_rows(guild_id)
    now = now_unix()
    lines = []
    for row in rows:
        seconds = max(0, int(row['expires_at']) - now)
        status = f'⏳ {seconds // 3600} h {(seconds % 3600) // 60} min' if seconds else '✅ Disponible'
        lines.append(f'⚔️ <@{row["user_id"]}> — {status}')
    description = '👥 **Jugadores registrados**\n\n' + ('\n'.join(lines) if lines else 'Todavía no hay jugadores registrados.')
    embed = discord.Embed(title='⚔️ HISPANIC GANG | PvP TIMER', description=description, color=BURGUNDY)
    embed.set_footer(text='⏱️ Cooldown PvP: 5 horas · Actualización cada 60 segundos')
    return embed


@bot.event
async def setup_hook():
    servidor_pruebas = discord.Object(id=1218989134366900325)

    bot.tree.copy_global_to(guild=servidor_pruebas)
    comandos = await bot.tree.sync(guild=servidor_pruebas)

    print(f"✅ {len(comandos)} comandos sincronizados en el servidor de pruebas")

@bot.tree.command(name='ping', description='Comprueba si el bot está funcionando')
async def ping(interaction: discord.Interaction):
    await interaction.response.send_message('🏓 ¡HISPANIC GANG está funcionando!', ephemeral=True)


@bot.tree.command(name='pvp', description='Inicia tu cooldown PvP de 5 horas')
@app_commands.guild_only()
async def pvp(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)
    try:
        guild_id, user_id = str(interaction.guild_id), str(interaction.user.id)
        existing = db.table('pvp_members').select('expires_at').eq('guild_id', guild_id).eq('user_id', user_id).limit(1).execute().data
        now = now_unix()
        if existing and int(existing[0]['expires_at']) > now:
            remaining = int(existing[0]['expires_at']) - now
            await interaction.followup.send(f'⏳ Ya tenés un cooldown activo: {remaining // 3600} h {(remaining % 3600) // 60} min restantes.', ephemeral=True)
            return
        db.table('pvp_members').upsert({'guild_id': guild_id, 'user_id': user_id, 'expires_at': now + COOLDOWN_SECONDS}, on_conflict='guild_id,user_id').execute()
        await interaction.followup.send('⚔️ ¡Cooldown PvP iniciado! Podrás volver a utilizarlo en 5 horas.', ephemeral=True)
    except Exception as exc:
        print(f'Error /pvp: {exc}', flush=True)
        await interaction.followup.send('❌ No pude guardar el cooldown. Probá de nuevo.', ephemeral=True)


@bot.tree.command(name='reset-pvp', description='Reinicia tu cooldown o el de otro jugador (administradores)')
@app_commands.describe(usuario='Jugador al que querés reiniciar el cooldown; omitilo para vos')
@app_commands.guild_only()
@app_commands.default_permissions(administrator=True)
async def reset_pvp(interaction: discord.Interaction, usuario: discord.Member | None = None):
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message('❌ Solo los administradores pueden usar este comando.', ephemeral=True)
        return
    await interaction.response.defer(ephemeral=True)
    target = usuario or interaction.user
    try:
        guild_id, user_id = str(interaction.guild_id), str(target.id)
        # El reset deja al jugador disponible, pero no lo registra si nunca usó /pvp.
        existing = db.table('pvp_members').select('user_id').eq('guild_id', guild_id).eq('user_id', user_id).limit(1).execute().data
        if existing:
            db.table('pvp_members').update({'expires_at': 0}).eq('guild_id', guild_id).eq('user_id', user_id).execute()
        await interaction.followup.send(f'✅ Cooldown de {target.mention} reiniciado.' if existing else f'ℹ️ {target.mention} todavía no está registrado en PvP.', ephemeral=True)
    except Exception as exc:
        print(f'Error /reset-pvp: {exc}', flush=True)
        await interaction.followup.send('❌ No pude reiniciar el cooldown.', ephemeral=True)


@bot.tree.command(name='panel-pvp', description='Publica un panel PvP que se actualiza automáticamente')
@app_commands.guild_only()
async def panel_pvp(interaction: discord.Interaction):
    await interaction.response.defer()
    try:
        embed = await asyncio.to_thread(make_embed, interaction.guild_id)
        message = await interaction.followup.send(embed=embed, wait=True)
        await asyncio.to_thread(lambda: db.table('pvp_panels').upsert({
            'message_id': str(message.id),
            'channel_id': str(message.channel.id),
            'guild_id': str(interaction.guild_id)
        }, on_conflict='message_id').execute())
    except Exception as exc:
        print(f'Error /panel-pvp: {exc}', flush=True)
        await interaction.followup.send('❌ No pude crear o registrar el panel.', ephemeral=True)


@tasks.loop(seconds=PANEL_UPDATE_SECONDS)
async def refresh_panels():
    try:
        panels = await asyncio.to_thread(lambda: db.table('pvp_panels').select('message_id,channel_id,guild_id').execute().data or [])
        for panel in panels:
            try:
                channel_id = int(panel['channel_id'])
                channel = bot.get_channel(channel_id) or await bot.fetch_channel(channel_id)
                message = await channel.fetch_message(int(panel['message_id']))
                embed = await asyncio.to_thread(make_embed, int(panel['guild_id']))
                await message.edit(embed=embed)
                await asyncio.sleep(0.3)
            except (discord.NotFound, discord.Forbidden):
                # Un panel borrado o inaccesible no debe detener los demás.
                print(f'Panel no disponible: {panel["message_id"]}', flush=True)
            except Exception as exc:
                print(f'Error actualizando panel {panel["message_id"]}: {exc}', flush=True)
    except Exception as exc:
        print(f'Error general actualizando paneles: {exc}', flush=True)


@refresh_panels.before_loop
async def before_refresh():
    await bot.wait_until_ready()


@bot.event
async def setup_hook():
    await bot.tree.sync()
    refresh_panels.start()


bot.run(TOKEN)
