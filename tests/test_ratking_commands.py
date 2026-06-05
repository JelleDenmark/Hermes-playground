import importlib.util
import os
import time

# locate commands.py in repo
repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
possible = [
    os.path.join(repo_root, 'ratking', 'commands.py'),
    os.path.join(repo_root, 'commands.py'),
    os.path.join(repo_root, 'ratking', 'commands', 'commands.py'),
]
cmds_path = None
for p in possible:
    if os.path.exists(p):
        cmds_path = p
        break

if not cmds_path:
    raise FileNotFoundError('Could not find ratking commands.py; tried: ' + ','.join(possible))

_spec = importlib.util.spec_from_file_location('ratking.commands', cmds_path)
commands = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(commands)

print('Loaded ratking.commands from', cmds_path)

# Register a regex command without saving to disk
commands.register_command('say', 'I hear: {0}', match='regex', pattern=r'^say\\s+(.+)$', save=False)
res = commands.get_response_for('!say hello world')
assert res is not None and res[0].startswith('I hear:'), f'Result unexpected: {res}'
print('Regex match OK ->', res[0])

# Test rate limiting helper (internal)
commands.register_command('rltest', 'ok', rate_limit=2, save=False)
user_id = 12345
# first call should not be rate-limited
limited = commands._rate_limited('rltest', user_id, 2)
assert limited is False
# second immediate call should be rate-limited
limited2 = commands._rate_limited('rltest', user_id, 2)
assert limited2 is True
# wait and verify it resets
time.sleep(2.1)
limited3 = commands._rate_limited('rltest', user_id, 2)
assert limited3 is False
print('Rate-limit helper OK')

print('All ratking command tests passed')
