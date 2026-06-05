import importlib.util
import os

# Find bot_clean/commands.py by searching upward from this file and from CWD
candidates = []
here = os.path.abspath(os.path.dirname(__file__))
for _ in range(6):
    candidates.append(os.path.join(here, 'bot_clean', 'commands.py'))
    here = os.path.dirname(here)

cwd = os.path.abspath(os.getcwd())
here = cwd
for _ in range(6):
    candidates.append(os.path.join(here, 'bot_clean', 'commands.py'))
    here = os.path.dirname(here)

cmds_path = None
for p in candidates:
    if os.path.exists(p):
        cmds_path = p
        break

if not cmds_path:
    raise FileNotFoundError('Could not find bot_clean/commands.py in candidates: ' + ','.join(candidates[:6]))

print('Using commands.py at', cmds_path)
_spec = importlib.util.spec_from_file_location('bot_clean.commands', cmds_path)
commands = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(commands)

print('Initial commands:', commands.list_commands())

# Use non-persistent register/unregister (save=False) to avoid touching disk
commands.register_command('temp', 'temp response {args}', save=False)
assert commands.get_response_for('!temp hello') == 'temp response hello'
print('Registered temp ->', commands.get_response_for('!temp hello'))

removed = commands.unregister_command('temp', save=False)
assert removed is True
assert commands.get_response_for('!temp hello') is None
print('Unregister temp OK')

# Test formatting with multiple args
commands.register_command('multi', 'first={0};rest={args}', save=False)
assert commands.get_response_for('!multi a b c') == 'first=a;rest=a b c'
print('Multi-arg formatting OK')

print('All run_bot_clean_tests checks passed')
