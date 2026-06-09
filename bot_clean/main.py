"""Minimal clean bot that uses bot_clean.commands and logs startup clearly.
Entry: python -u bot_clean/main.py
"""
import os
import sys
# Ensure repo root is on sys.path so package imports work when running file directly
_repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if _repo_root not in sys.path:
    sys.path.insert(0, _repo_root)

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
# Ready check manager
from bot_clean.ready_check import ReadyCheckManager

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

# instantiate ready-check manager
repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
ready_manager = ReadyCheckManager(client, LOG, repo_root=repo_root)


def _write_heartbeat():
    try:
        with open(heartbeat_path, 'w', encoding='utf-8') as f:
            f.write(f'OK {datetime.utcnow().isoformat()}')
    except Exception:
        LOG.exception('Failed to write heartbeat')


def _write_start_marker(tag: str):
    try:
        repo = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
        path = os.path.join(repo, f'bot_start_marker_{tag}.txt')
        with open(path, 'w', encoding='utf-8') as f:
            f.write(f'{tag} {datetime.utcnow().isoformat()}\n')
    except Exception:
        LOG.exception('Failed to write start marker')


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

    # trigger endpoint: POST /trigger_ready_check  {duration_seconds, required, channel_name}
    async def trigger_handler(request):
        try:
            data = await request.json()
        except Exception:
            data = {}
        duration = int(data.get('duration_seconds', 300))
        required = int(data.get('required', ready_manager.required))
        channel_name = data.get('channel_name', 'hermes')
        # start check in background
        try:
            asyncio.create_task(ready_manager.start_check(duration_seconds=duration, required=required, channel_name=channel_name))
            return web.json_response({'status': 'started', 'duration': duration, 'required': required, 'channel': channel_name})
        except Exception as e:
            LOG.exception('Failed to start ready check from HTTP trigger')
            return web.json_response({'status': 'error', 'error': str(e)}, status=500)

    app.router.add_post(f'{prefix}/trigger_ready_check', trigger_handler)

    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, host=host, port=port)
    await site.start()
    LOG.info(f'Health server listening on http://{host}:{port}{prefix}/ready and /health and /trigger_ready_check')


async def _recap_worker(interval: int = 30):
    """Background worker that processes one recap job every `interval` seconds
    and posts the generated recap to the #hermes channel."""
    # import here to avoid import-time side-effects
    try:
        from features.cs2_recap.process_queue import process_one
    except Exception:
        LOG.exception('Failed to import recap process_one')
        return
    from discord.utils import get
    while True:
        try:
            item = process_one()
            if item:
                share = item.get('sharecode')
                user = item.get('user')
                recap_text = item.get('recap_text')
                # find channel named 'hermes'
                chan = get(client.get_all_channels(), name='hermes')
                if chan:
                    try:
                        header = f"Recap for {share} (requested by {user})"
                        # send as codeblock to preserve formatting
                        await chan.send(header + "\n```" + recap_text + "```")
                        LOG.info('Posted recap %s to #%s', share, chan.name)
                    except Exception:
                        LOG.exception('Failed to send recap to channel')
                else:
                    LOG.warning('No channel named hermes found; recap saved to %s', item.get('out_path'))
        except Exception:
            LOG.exception('recap worker exception')
        await asyncio.sleep(interval)


@client.event
async def on_ready():
    # Print identity and flush
    msg = f"Logged in as {client.user} (id={client.user.id})"
    print(msg, flush=True)
    LOG.info(msg)
    _write_heartbeat()
    _write_start_marker('on_ready')
    try:
        import os as __os_low
        fd = __os_low.open(r'C:\\Users\\jespe\
atking\\startup_fd_marker.log', __os_low.O_CREAT | __os_low.O_WRONLY | __os_low.O_APPEND)
        __os_low.write(fd, f'ON_READY pid={__os_low.getpid()} env_present={bool(__os_low.environ.get("DISCORD_BOT_TOKEN"))}\\n'.encode('utf-8'))
        __os_low.close(fd)
    except Exception:
        pass
    # start background heartbeat task
    try:
        client.loop.create_task(_heartbeat_loop(60))
    except Exception:
        LOG.exception('Failed to start heartbeat loop')
    # Feature flags for optional heavy services
    health_port = int(os.getenv('HEALTH_PORT', '8080'))
    health_host = os.getenv('HEALTH_HOST', '127.0.0.1')
    health_prefix = os.getenv('HEALTH_PREFIX', '')

    feat_health = os.getenv('FEATURE_HEALTH', 'false').lower() == 'true'
    feat_ready = os.getenv('FEATURE_READY_CHECK', 'false').lower() == 'true'
    feat_recap = os.getenv('FEATURE_RECAP', 'false').lower() == 'true'

    LOG.info('Feature flags: FEATURE_HEALTH=%s FEATURE_READY_CHECK=%s FEATURE_RECAP=%s', feat_health, feat_ready, feat_recap)

    # start HTTP health server in the bot loop if feature enabled
    if feat_health:
        try:
            LOG.info('Scheduling health server task (host=%s port=%s prefix=%s)', health_host, health_port, health_prefix)
            _write_start_marker('scheduling_health')
            client.loop.create_task(_start_health_server(host=health_host, port=health_port, prefix=health_prefix))
            LOG.info('Health server task scheduled')
        except Exception:
            LOG.exception('Failed to start health server')
    else:
        LOG.info('Health server disabled via FEATURE_HEALTH (default false)')

    # start ready_check trigger watcher only if feature enabled
    if feat_ready:
        try:
            LOG.info('Scheduling ready_check trigger watcher task (poll=5s)')
            _write_start_marker('scheduling_trigger_watcher')
            client.loop.create_task(ready_manager.trigger_watcher(poll_interval=5))
            LOG.info('ready_check trigger watcher task scheduled')
        except Exception:
            LOG.exception('Failed to start ready_check trigger watcher')
    else:
        LOG.info('Ready check trigger watcher disabled via FEATURE_READY_CHECK (default false)')

    # start recap worker only if feature enabled
    if feat_recap:
        try:
            LOG.info('Scheduling recap worker task (interval=30s)')
            _write_start_marker('scheduling_recap_worker')
            client.loop.create_task(_recap_worker(30))
            LOG.info('Recap worker task scheduled')
        except Exception:
            LOG.exception('Failed to start recap worker')
    else:
        LOG.info('Recap worker disabled via FEATURE_RECAP (default false)')


@client.event
async def on_message(message):
    try:
        if getattr(message.author, 'bot', False):
            return
        # first give ready manager a chance
        handled = await ready_manager.handle_message(message)
        if handled:
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
        res = commands.get_response_for(content)
        if res:
            # res is (response_text, meta)
            try:
                response_text, meta = res
            except Exception:
                # fallback for older shape
                response_text = res if isinstance(res, str) else str(res)
                meta = {}

            # If this is a recap command, enqueue job in the cs2_recap queue
            cmd_key = meta.get('command_key')
            if cmd_key in ('recap', '/recap'):
                # extract sharecode from args or regex groups
                share = None
                args = meta.get('args') or []
                if args:
                    share = args[0]
                else:
                    groups = meta.get('matched_groups') or ()
                    if groups:
                        share = groups[0]
                if share:
                    try:
                        from features.cs2_recap.process_queue import enqueue
                        enqueue(str(message.author), share)
                        LOG.info('Enqueued recap %s requested by %s', share, message.author)
                    except Exception:
                        LOG.exception('Failed to enqueue recap')

            # send the configured response text
            try:
                await message.channel.send(response_text)
            except Exception:
                LOG.exception('Failed to send response for command %s', cmd_key)

    except Exception as e:
        LOG.exception('handler exception')
        print('handler exception:', e)
        traceback.print_exc()


def main():
    # Debug: force early visible output and ensure logging goes to stdout + file so we can diagnose silent starts
    import sys, logging
    try:
        print('DEBUG: main() start', flush=True)
        print('DEBUG: DISCORD_BOT_TOKEN present (env):', bool(__import__('os').environ.get('DISCORD_BOT_TOKEN')), flush=True)
    except Exception:
        pass
    try:
        # Remove any preconfigured handlers and reconfigure logging to stdout + file
        for _h in logging.root.handlers[:]:
            logging.root.removeHandler(_h)
        logging.basicConfig(level=logging.INFO,
                            format='%(asctime)s %(levelname)s %(name)s: %(message)s',
                            handlers=[logging.StreamHandler(sys.stdout), logging.FileHandler(log_file, encoding='utf-8')])
        logging.getLogger().info('DEBUG: logging configured to stdout and %s', log_file)
    except Exception as _e:
        try:
            print('DEBUG: logging config failed:', _e, flush=True)
        except Exception:
            pass

    # Load DISCORD_BOT_TOKEN from environment or fallback to the user's Hermes .env file
    token = os.getenv('DISCORD_BOT_TOKEN')
    if not token:
        ENV_PATH = r'C:\Users\jespe\AppData\Local\hermes\.env'
        try:
            if os.path.exists(ENV_PATH):
                with open(ENV_PATH, 'r', encoding='utf-8') as _f:
                    for _line in _f:
                        _line = _line.strip()
                        if not _line or _line.startswith('#'):
                            continue
                        if '=' not in _line:
                            continue
                        _k, _v = _line.split('=', 1)
                        _k = _k.strip()
                        _v = _v.strip().strip('"').strip("'")
                        if _k == 'DISCORD_BOT_TOKEN' and _v:
                            os.environ['DISCORD_BOT_TOKEN'] = _v
                            token = _v
                            break

        except Exception:
            # Keep failing silently here; main will check token and abort with a clear message
            token = os.getenv('DISCORD_BOT_TOKEN')

        # Fall back: try to read token from hermes .env file (handles cases where
        # the startup script didn't source the file).
        try:
            env_path = os.path.expanduser(r'C:\\Users\\jespe\\AppData\\Local\\hermes\\.env')
            with open(env_path, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith('#'):
                        continue
                    if line.startswith('DISCORD_BOT_TOKEN='):
                        token = line.split('=', 1)[1].strip()
                        break
                    # Accept older key name as fallback
                    if line.startswith('DISCORD_TOKEN=') and not token:
                        token = line.split('=', 1)[1].strip()
        except Exception:
            # Ignore file errors; token will remain None and the program will abort below.
            pass

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
    _write_start_marker('client_run_called')
    print('Starting bot (connecting...)', flush=True)
    try:
        try:
            with open(r'C:\Users\jespe\ratking\startup_marker_force.log','a',encoding='utf-8') as _mf:
                _mf.write(f'BEFORE_CLIENT_RUN pid={__import__("os").getpid()} env_present={bool(__import__("os").environ.get("DISCORD_BOT_TOKEN"))}\n')
        except Exception:
            pass
        client.run(token)
    except Exception:
        LOG.exception('client.run failed')
        traceback.print_exc()


if __name__ == '__main__':
    main()
