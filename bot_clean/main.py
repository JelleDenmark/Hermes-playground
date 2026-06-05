"""Minimal clean bot that uses bot_clean.commands and logs startup clearly.
Entry: python -u bot_clean/main.py
"""
import os
import sys
import asyncio
import traceback
import logging
import importlib.util
from logging.handlers import RotatingFileHandler
from datetime import datetime

try:
    import discord
except Exception:
    print("discord.py not installed")
    raise

# Load commands module from repo root commands.py
commands_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'commands.py'))
_spec = importlib.util.spec_from_file_location('ratking.commands', commands_path)
commands = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(commands)

# Health checks module
from bot_clean.health import Health

LOG = logging.getLogger('ratking_clean')
log_file = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'ratking_bot_clean.log'))
handler = RotatingFileHandler(log_file, maxBytes=1_000_000, backupCount=3, encoding='utf-8')
handler.setFormatter(logging.Formatter('%(asctime)s %(levelname)s %(message)s'))
LOG.setLevel(logging.INFO)
LOG.addHandler(handler)
# also log to stdout
console = logging.StreamHandler(sys.stdout)
console.setFormatter(logging.Formatter('%(asctime)s %(levelname)s %(message)s'))
LOG.addHandler(console)

PREFIX = commands.DEFAULT_PREFIX

# Ensure default command exists
commands.register_command('greeting', 'hello')

intents = discord.Intents.default()
intents.message_content = True
client = discord.Client(intents=intents)

heartbeat_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'ratking_heartbeat.txt'))
log_path = log_file

# instantiate health manager
health = Health(heartbeat_path=heartbeat_path, log_path=log_path, commands_module=commands)


def _write_heartbeat():
    try:
        with open(heartbeat_path, 'w', encoding='utf-8') as f:
            f.write(f'OK {datetime.utcnow().isoformat()}')
    except Exception:
        LOG.exception('Failed to write heartbeat')


async def _heartbeat_loop(interval: int = 60):
    while True:
        _write_heartbeat()
        await asyncio.sleep(interval)


async def _start_health_server(host: str = '127.0.0.1', port: int = 8080, prefix: str = ''):
    try:
        from aiohttp import web
    except Exception:
        LOG.info('aiohttp not installed; health HTTP server disabled')
        return
    app = health.make_aiohttp_app(prefix=prefix)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, host=host, port=port)
    await site.start()
    LOG.info(f'Health server listening on http://{host}:{port}{prefix}/ready and /health')


@client.event
async def on_ready():
    # Print identity and flush
    msg = f"Logged in as {client.user} (id={client.user.id})"
    print(msg, flush=True)
    LOG.info(msg)
    _write_heartbeat()
    # start background heartbeat task
    try:
        client.loop.create_task(_heartbeat_loop(60))
    except Exception:
        LOG.exception('Failed to start heartbeat loop')
    # start HTTP health server in the bot loop if requested
    health_port = int(os.getenv('HEALTH_PORT', '8080'))
    health_host = os.getenv('HEALTH_HOST', '127.0.0.1')
    health_prefix = os.getenv('HEALTH_PREFIX', '')
    try:
        client.loop.create_task(_start_health_server(host=health_host, port=health_port, prefix=health_prefix))
    except Exception:
        LOG.exception('Failed to start health server')


@client.event
async def on_message(message):
    try:
        if getattr(message.author, 'bot', False):
            return
        # admin add command: !addcmd name response
        content = (message.content or '').strip()
        if content.startswith(f"{PREFIX}addcmd"):
            # permission check: manage_guild
            perms = getattr(message.author, 'guild_permissions', None)
            if not getattr(perms, 'manage_guild', False):
                await message.channel.send('You need Manage Server permission to add commands.')
                return
            parts = content.split(maxsplit=2)
            if len(parts) < 3:
                await message.channel.send('Usage: !addcmd name response')
                return
            name = parts[1].lstrip(PREFIX)
            response = parts[2]
            commands.register_command(name, response)
            await message.channel.send(f'Registered command {PREFIX}{name} -> {response}')
            return

        # admin delete command: !delcmd name
        if content.startswith(f"{PREFIX}delcmd"):
            perms = getattr(message.author, 'guild_permissions', None)
            if not getattr(perms, 'manage_guild', False):
                await message.channel.send('You need Manage Server permission to delete commands.')
                return
            parts = content.split(maxsplit=1)
            if len(parts) < 2:
                await message.channel.send('Usage: !delcmd name')
                return
            name = parts[1].lstrip(PREFIX)
            existed = commands.unregister_command(name)
            if existed:
                await message.channel.send(f'Removed command {PREFIX}{name}')
            else:
                await message.channel.send(f'Command {PREFIX}{name} not found')
            return

        # status command
        if content == f"{PREFIX}status":
            st = health.get_ready_status()
            lines = [f"{k}: {v}" for k, v in st.items()]
            await message.channel.send('Status:\n' + '\n'.join(lines))
            return

        # dynamic help: always build from live commands to avoid stale help
        if content == f"{PREFIX}help":
            cmds = commands.list_commands()
            lines = [f"{k}: {v}" for k, v in cmds.items()]
            await message.channel.send('Commands:\n' + '\n'.join(lines))
            return

        if content == f"{PREFIX}commands":
            cmds = commands.list_commands()
            lines = [f"{k}: {v}" for k, v in cmds.items()]
            await message.channel.send('Commands:\n' + '\n'.join(lines))
            return

        # delegate to commands.get_response_for
        resp = commands.get_response_for(content)
        if resp:
            await message.channel.send(resp)
    except Exception as e:
        LOG.exception('handler exception')
        print('handler exception:', e)
        traceback.print_exc()


def main():
    token = os.getenv('DISCORD_BOT_TOKEN')
    if not token:
        print('Missing DISCORD_BOT_TOKEN environment variable. Aborting.', flush=True)
        return

    # run startup self-checks
    ok = health.run_self_checks()
    if not ok:
        LOG.error('Startup self-checks failed: %s', health.get_ready_status())
    else:
        LOG.info('Startup self-checks passed')

    LOG.info('Starting bot (connecting...)')
    print('Starting bot (connecting...)', flush=True)
    try:
        client.run(token)
    except Exception:
        LOG.exception('client.run failed')
        traceback.print_exc()


if __name__ == '__main__':
    main()
