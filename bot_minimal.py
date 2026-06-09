"""Minimal deterministic Discord bot for RatKing — exact-match commands from commands.json

Run: python -u bot_minimal.py

Features:
- Loads commands.json at startup (exact-match only)
- Admin-only: !reload-commands to re-read commands.json
- No background workers, no watchers, no HTTP server
"""
import os
import sys
import json
import logging

try:
    import discord
except Exception:
    print('discord.py not installed', file=sys.stderr)
    raise

ROOT = os.path.abspath(os.path.dirname(__file__))
COMMANDS_PATH = os.path.join(ROOT, 'commands.json')
PREFIX = '!'

LOG = logging.getLogger('ratking_minimal')
LOG.setLevel(logging.INFO)
handler = logging.StreamHandler(sys.stdout)
handler.setFormatter(logging.Formatter('%(asctime)s %(levelname)s %(message)s'))
LOG.addHandler(handler)

def load_commands():
    try:
        with open(COMMANDS_PATH, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except Exception as e:
        LOG.exception('Failed to load commands.json')
        return {}
    # normalize keys: strip prefix
    out = {}
    for k, v in data.items():
        name = str(k).lstrip(PREFIX)
        # support shorthand string responses
        if isinstance(v, str):
            out[name] = {'response': v}
        elif isinstance(v, dict):
            out[name] = {'response': v.get('response', '')}
        else:
            out[name] = {'response': str(v)}
    return out

COMMANDS = load_commands()

intents = discord.Intents.default()
intents.message_content = True
client = discord.Client(intents=intents)

@client.event
async def on_ready():
    print(f'Logged in as {client.user} (id={client.user.id})', flush=True)
    LOG.info('Bot ready')

@client.event
async def on_message(message):
    try:
        if getattr(message.author, 'bot', False):
            return
    except Exception:
        return

    content = (message.content or '').strip()
    if not content:
        return

    # admin reload
    if content == f"{PREFIX}reload-commands":
        perms = getattr(message.author, 'guild_permissions', None)
        if not getattr(perms, 'manage_guild', False):
            await message.channel.send('You need Manage Server permission to reload commands.')
            return
        global COMMANDS
        COMMANDS = load_commands()
        await message.channel.send('Commands reloaded. Total: %d' % len(COMMANDS))
        return

    # simple exact-match
    if content.startswith(PREFIX):
        after = content[len(PREFIX):].strip()
        if not after:
            return
        parts = after.split()
        token = parts[0]
        entry = COMMANDS.get(token)
        if entry:
            resp = entry.get('response', '')
            # try basic formatting with args
            args = parts[1:]
            try:
                out = resp.format(*args, args=' '.join(args))
            except Exception:
                out = resp
            try:
                await message.channel.send(out)
            except Exception:
                LOG.exception('Failed to send response')

if __name__ == '__main__':
    token = os.getenv('DISCORD_BOT_TOKEN')
    if not token:
        print('DISCORD_BOT_TOKEN not set in environment. Exiting.', file=sys.stderr)
        sys.exit(1)
    client.run(token)
