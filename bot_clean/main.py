"""Minimal clean bot that uses bot_clean.commands and logs startup clearly.
Entry: python -u bot_clean/main.py
"""
import os
import sys
import asyncio
import traceback
import logging
import importlib.util

try:
    import discord
except Exception:
    print("discord.py not installed")
    raise

# Load commands module by path to avoid package import issues when running as script
commands_path = os.path.join(os.path.dirname(__file__), 'commands.py')
_spec = importlib.util.spec_from_file_location('bot_clean.commands', commands_path)
commands = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(commands)

LOG = logging.getLogger('ratking_clean')
logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')

PREFIX = commands.DEFAULT_PREFIX

# Ensure default command exists
commands.register_command('greeting', 'hello')

intents = discord.Intents.default()
intents.message_content = True
client = discord.Client(intents=intents)


@client.event
async def on_ready():
    # Print identity and flush
    msg = f"Logged in as {client.user} (id={client.user.id})"
    print(msg, flush=True)


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
        print('handler exception:', e)
        traceback.print_exc()


def main():
    token = os.getenv('DISCORD_BOT_TOKEN')
    if not token:
        print('Missing DISCORD_BOT_TOKEN environment variable. Aborting.', flush=True)
        return
    print('Starting bot (connecting...)', flush=True)
    try:
        client.run(token)
    except Exception:
        traceback.print_exc()


if __name__ == '__main__':
    main()
