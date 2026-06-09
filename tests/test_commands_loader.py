#!/usr/bin/env python3
"""Simple smoke test to verify commands loader exposes expected keys.

Run with: python tests/test_commands_loader.py
"""
import os
import sys

# Ensure repo root is on sys.path
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import commands


def main():
    # Force a reload to be explicit
    try:
        commands._load_commands()
    except Exception:
        # If reload fails, allow assertions to catch missing keys
        pass

    assert 'greeting' in commands.COMMANDS, "Expected 'greeting' in commands.COMMANDS"
    assert 'ping' in commands.COMMANDS, "Expected 'ping' in commands.COMMANDS"
    print("OK: commands loaded contain 'greeting' and 'ping'")


if __name__ == '__main__':
    main()
