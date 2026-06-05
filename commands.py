"""RatKing command system with JSON persistence, auto-reload, permissions, rate-limits, and regex support.

Schema supported in commands.json (backwards compatible):
- Simple form (backwards compatible): {"!greeting": "hello"}
- Full form per-command (value is an object):
  {
    "trigger": "!echo",            # optional; key may be used instead
    "response": "You said: {args}",
    "match": "exact"|"regex",    # default exact
    "pattern": "^echo\\s+(.*)", # required for regex
    "permission": "none"|"manage_guild"|"administrator"|"owner",
    "rate_limit": 5,                # seconds per-user
    "case_sensitive": false
  }

Notes:
- Triggers are stored without the prefix internally. DEFAULT_PREFIX='!'.
- Auto-reload watches commands.json for changes and reloads within ~1s.
- Rate-limits are per-user per-command.

This module is written to be import-safe in a Discord bot; it spawns a
background daemon thread for file-watching.
"""
from typing import Optional, Dict, Tuple, List, Any
from pathlib import Path
import json
import threading
import time
import re

DEFAULT_PREFIX = "!"

_commands_file = Path(__file__).parent / "commands.json"
_lock = threading.Lock()

# Internal command structure:
# key -> {
#   'response': str,
#   'match': 'exact'|'regex',
#   'pattern': Optional[re.Pattern],
#   'permission': 'none'|'manage_guild'|'administrator'|'owner',
#   'rate_limit': int|None,
#   'case_sensitive': bool
# }
COMMANDS: Dict[str, Dict[str, Any]] = {}

# per-user per-command last-used timestamp
_LAST_USED: Dict[Tuple[str, int], float] = {}


def _load_commands() -> None:
    """Load commands from JSON file into COMMANDS (thread-safe)."""
    global COMMANDS
    data = {}
    if _commands_file.exists():
        try:
            data = json.loads(_commands_file.read_text(encoding="utf-8"))
        except Exception:
            # If file corrupted, ignore load
            return
    # data may be {"!greeting": "hello"} or {"greet": {...}}
    new_map: Dict[str, Dict[str, Any]] = {}

    for key, val in data.items():
        # normalize key and support full object or string shorthand
        norm_key = str(key).lstrip(DEFAULT_PREFIX)
        if isinstance(val, str):
            entry = {
                'response': val,
                'match': 'exact',
                'pattern': None,
                'permission': 'none',
                'rate_limit': None,
                'case_sensitive': False,
            }
            new_map[norm_key] = entry
            continue
        if isinstance(val, dict):
            resp = val.get('response') or val.get('reply') or ''
            match = val.get('match', 'exact')
            pat = None
            if match == 'regex':
                pattern_text = val.get('pattern') or val.get('regex')
                try:
                    flags = 0 if val.get('case_sensitive', False) else re.IGNORECASE
                    pat = re.compile(pattern_text, flags) if pattern_text else None
                except Exception:
                    pat = None
            entry = {
                'response': resp,
                'match': match,
                'pattern': pat,
                'permission': val.get('permission', 'none'),
                'rate_limit': int(val['rate_limit']) if 'rate_limit' in val else None,
                'case_sensitive': bool(val.get('case_sensitive', False)),
            }
            new_map[norm_key] = entry
            continue
        # unsupported type -> ignore

    with _lock:
        COMMANDS = new_map


def _save_commands() -> None:
    """Persist COMMANDS back to the JSON file in a compatible shape.

    This writes a mapping of prefixed triggers to either string responses
    (for simple entries) or objects when non-default fields are present.
    """
    serial: Dict[str, Any] = {}
    with _lock:
        for key, entry in COMMANDS.items():
            pref = DEFAULT_PREFIX + key
            # if entry is default shape, save shorthand
            if (entry.get('match') == 'exact' and entry.get('permission') in (None, 'none')
                    and not entry.get('rate_limit') and not entry.get('case_sensitive')):
                serial[pref] = entry.get('response', '')
            else:
                obj = {
                    'response': entry.get('response', ''),
                    'match': entry.get('match', 'exact'),
                }
                if entry.get('match') == 'regex' and entry.get('pattern') is not None:
                    obj['pattern'] = entry['pattern'].pattern
                if entry.get('permission') and entry.get('permission') != 'none':
                    obj['permission'] = entry.get('permission')
                if entry.get('rate_limit'):
                    obj['rate_limit'] = entry.get('rate_limit')
                if entry.get('case_sensitive'):
                    obj['case_sensitive'] = True
                serial[pref] = obj
    tmp = _commands_file.with_suffix('.tmp')
    try:
        with tmp.open('w', encoding='utf-8') as f:
            json.dump(serial, f, indent=2, ensure_ascii=False)
        tmp.replace(_commands_file)
    except Exception:
        pass


# initialize at import
_load_commands()


# File watcher thread: polls mtime and reloads if changed
def _watcher_loop(poll_interval: float = 1.0):
    last_mtime = _commands_file.stat().st_mtime if _commands_file.exists() else None
    while True:
        try:
            if _commands_file.exists():
                mtime = _commands_file.stat().st_mtime
                if last_mtime is None or mtime != last_mtime:
                    _load_commands()
                    last_mtime = mtime
        except Exception:
            # ignore transient FS errors
            pass
        time.sleep(poll_interval)


_watcher_thread = threading.Thread(target=_watcher_loop, daemon=True, name='ratking-cmd-watcher')
_watcher_thread.start()


# Public API

def register_command(trigger: str, response: str, match: str = 'exact', pattern: Optional[str] = None,
                     permission: str = 'none', rate_limit: Optional[int] = None, save: bool = True) -> None:
    """Register or update a command trigger.

    trigger: command name with or without prefix (e.g. '!greeting' or 'greeting')
    response: text to send when trigger matches. May include format placeholders
              like {0}, {1}, {args}.
    match: 'exact' or 'regex'
    pattern: regex pattern text when match=='regex'
    permission: 'none'|'manage_guild'|'administrator'|'owner'
    rate_limit: seconds per-user between uses (None => no limit)
    save: whether to persist to file immediately
    """
    if not trigger:
        raise ValueError('trigger must be a non-empty string')
    key = trigger.lstrip(DEFAULT_PREFIX).strip()
    entry: Dict[str, Any] = {
        'response': response,
        'match': match,
        'pattern': re.compile(pattern) if match == 'regex' and pattern else None,
        'permission': permission,
        'rate_limit': int(rate_limit) if rate_limit else None,
        'case_sensitive': False,
    }
    with _lock:
        COMMANDS[key] = entry
        if save:
            _save_commands()


def unregister_command(trigger: str, save: bool = True) -> bool:
    key = trigger.lstrip(DEFAULT_PREFIX).strip()
    with _lock:
        existed = COMMANDS.pop(key, None) is not None
        if existed and save:
            _save_commands()
        return existed


def list_commands() -> Dict[str, Dict[str, Any]]:
    with _lock:
        # return shallow copy; patterns are not JSON serializable but callers
        # generally only need response and metadata
        return {DEFAULT_PREFIX + k: {k2: (v2.pattern if k2 == 'pattern' and isinstance(v2, re.Pattern) else v2)
                                     for k2, v2 in entry.items()}
                for k, entry in COMMANDS.items()}


def parse_message(content: str) -> Optional[Tuple[str, List[str], str]]:
    """Parse content and return (command_key, args, raw_after_prefix).

    Returns None if message doesn't start with DEFAULT_PREFIX.
    """
    if not content:
        return None
    text = content.strip()
    if not text.startswith(DEFAULT_PREFIX):
        return None
    after = text[len(DEFAULT_PREFIX):].lstrip()
    if not after:
        return None
    parts = after.split()
    cmd = parts[0]
    args = parts[1:]
    return cmd, args, after


def _check_permission(message, permission: str) -> bool:
    if not permission or permission == 'none':
        return True
    # guild-only checks
    guild = getattr(message, 'guild', None)
    if guild is None:
        return False
    perm = permission
    try:
        if perm == 'manage_guild':
            return getattr(message.author.guild_permissions, 'manage_guild', False)
        if perm == 'administrator':
            return getattr(message.author.guild_permissions, 'administrator', False)
        if perm == 'owner':
            # guild.owner_id available on most versions
            owner_id = getattr(guild, 'owner_id', None)
            if owner_id is None:
                try:
                    return message.author == guild.owner
                except Exception:
                    return False
            return getattr(message.author, 'id', None) == owner_id
    except Exception:
        return False
    return False


def _rate_limited(command_key: str, user_id: int, rate_limit: Optional[int]) -> bool:
    if not rate_limit:
        return False
    now = time.time()
    key = (command_key, user_id)
    last = _LAST_USED.get(key)
    if last and (now - last) < rate_limit:
        return True
    _LAST_USED[key] = now
    return False


def get_response_for(content: str, author_id: Optional[int] = None) -> Optional[Tuple[str, Dict[str, Any]]]:
    """Return (response, meta) for the given message content, or None.

    meta includes 'command_key' and 'matched_groups' for regex matches.
    """
    parsed = parse_message(content)
    if not parsed:
        return None
    cmd_token, args, raw_after = parsed

    with _lock:
        # First try exact match on token
        entry = COMMANDS.get(cmd_token)
        if entry:
            template = entry.get('response')
            try:
                formatted = template.format(*args, args=' '.join(args))
            except Exception:
                formatted = template
            return formatted, {'command_key': cmd_token, 'entry': entry, 'args': args}

        # Then try regex matches across entries that have regex
        for key, ent in COMMANDS.items():
            if ent.get('match') != 'regex' or not ent.get('pattern'):
                continue
            pat: re.Pattern = ent['pattern']
            m = pat.match(raw_after)
            if not m:
                continue
            # format with groups and args
            groups = m.groups()
            template = ent.get('response', '')
            try:
                formatted = template.format(*groups, args=' '.join(args))
            except Exception:
                formatted = template
            return formatted, {'command_key': key, 'entry': ent, 'matched_groups': groups, 'args': args}

    return None


async def handle_message(message) -> Optional[str]:
    """Handle an incoming message object; enforces permissions and rate limits.

    Returns the response text if sent, or None.
    """
    try:
        if getattr(message.author, 'bot', False):
            return None
    except Exception:
        pass

    raw = getattr(message, 'content', '')
    res = get_response_for(raw, author_id=getattr(message.author, 'id', None))
    if not res:
        return None
    response_text, meta = res
    cmd_key = meta.get('command_key')
    entry = meta.get('entry', {})

    # permission check
    perm = entry.get('permission', 'none')
    if not _check_permission(message, perm):
        try:
            await message.channel.send('Permission denied for that command.')
        except Exception:
            pass
        return None

    # rate limit check
    user_id = getattr(message.author, 'id', None)
    if _rate_limited(cmd_key, user_id or 0, entry.get('rate_limit')):
        try:
            await message.channel.send('You are being rate-limited. Try again later.')
        except Exception:
            pass
        return None

    # send
    send = getattr(getattr(message, 'channel', None), 'send', None)
    if send is not None:
        try:
            await send(response_text)
            return response_text
        except Exception:
            return None

    return response_text
