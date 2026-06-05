import os
import sys
import tempfile
import importlib.util

# load root commands module for use in checks
repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
# ensure repo root on sys.path so package imports succeed when running this script directly
if repo_root not in sys.path:
    sys.path.insert(0, repo_root)

cmds_path = os.path.join(repo_root, 'commands.py')
_spec = importlib.util.spec_from_file_location('ratking.commands', cmds_path)
commands = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(commands)

# Ensure token present for check
os.environ['DISCORD_BOT_TOKEN'] = 'dummy-token'

# Import health module from bot_clean (to be implemented)
from bot_clean import health

with tempfile.TemporaryDirectory() as td:
    hb = os.path.join(td, 'hb.txt')
    logf = os.path.join(td, 'bot.log')
    h = health.Health(heartbeat_path=hb, log_path=logf, commands_module=commands)
    ok = h.run_self_checks()
    assert ok is True, 'self checks should pass'
    st = h.get_ready_status()
    assert st['token'] is True
    assert st['commands_loaded'] is True
    assert st['heartbeat_writable'] is True
    assert st['log_writable'] is True
    print('Health self-checks passed')
