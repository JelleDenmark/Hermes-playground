import os
import time
from datetime import datetime
from typing import Any, Dict, Optional

class Health:
    """Health and readiness checks for the bot.

    - run_self_checks() performs startup readiness checks and sets self.ready.
    - get_ready_status() returns a dict with detailed checks.
    - get_health_status() returns liveness info (heartbeat timestamp).
    """
    def __init__(self, heartbeat_path: str, log_path: str, commands_module: Any, heartbeat_interval: int = 60):
        self.heartbeat_path = heartbeat_path
        self.log_path = log_path
        self.commands_module = commands_module
        self.heartbeat_interval = heartbeat_interval
        self.ready = False
        self._last_heartbeat: Optional[float] = None

    def _check_token(self) -> bool:
        return bool(os.getenv('DISCORD_BOT_TOKEN'))

    def _check_commands(self) -> bool:
        try:
            cmds = None
            # commands_module may expose list_commands()
            if hasattr(self.commands_module, 'list_commands'):
                cmds = self.commands_module.list_commands()
            # consider loaded if it's a dict (may be empty but that's acceptable)
            return isinstance(cmds, dict)
        except Exception:
            return False

    def _check_heartbeat_writable(self) -> bool:
        try:
            d = os.path.dirname(self.heartbeat_path)
            if d and not os.path.exists(d):
                os.makedirs(d, exist_ok=True)
            with open(self.heartbeat_path, 'w', encoding='utf-8') as f:
                f.write(f'OK {datetime.utcnow().isoformat()}')
            self._last_heartbeat = os.path.getmtime(self.heartbeat_path)
            return True
        except Exception:
            return False

    def _check_log_writable(self) -> bool:
        try:
            d = os.path.dirname(self.log_path)
            if d and not os.path.exists(d):
                os.makedirs(d, exist_ok=True)
            with open(self.log_path, 'a', encoding='utf-8') as f:
                f.write(f'[{datetime.utcnow().isoformat()}] health-check\n')
            return True
        except Exception:
            return False

    def run_self_checks(self) -> bool:
        """Run startup checks. Returns True if all required checks pass."""
        token_ok = self._check_token()
        cmds_ok = self._check_commands()
        hb_ok = self._check_heartbeat_writable()
        log_ok = self._check_log_writable()

        self.ready = all([token_ok, cmds_ok, hb_ok, log_ok])
        return self.ready

    def get_ready_status(self) -> Dict[str, Any]:
        return {
            'token': self._check_token(),
            'commands_loaded': self._check_commands(),
            'heartbeat_writable': self._check_heartbeat_writable(),
            'log_writable': self._check_log_writable(),
            'ready': self.ready,
        }

    def get_health_status(self) -> Dict[str, Any]:
        hb_mtime = None
        try:
            if os.path.exists(self.heartbeat_path):
                hb_mtime = os.path.getmtime(self.heartbeat_path)
        except Exception:
            hb_mtime = None
        return {
            'alive': True,
            'heartbeat_mtime': hb_mtime,
            'heartbeat_age_seconds': (time.time() - hb_mtime) if hb_mtime else None,
        }

    # aiohttp helpers (optional)
    def make_aiohttp_app(self, prefix: str = ''):
        try:
            from aiohttp import web
        except Exception:
            raise
        app = web.Application()
        async def ready_handler(request):
            return web.json_response(self.get_ready_status())
        async def health_handler(request):
            return web.json_response(self.get_health_status())
        app.router.add_get(f'{prefix}/ready', ready_handler)
        app.router.add_get(f'{prefix}/health', health_handler)
        return app
