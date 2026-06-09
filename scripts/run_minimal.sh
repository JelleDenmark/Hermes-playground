#!/usr/bin/env bash
set -e
# Run minimal bot: load DISCORD_BOT_TOKEN from Hermes .env and run bot_minimal
cd /c/Users/jespe/ratking
set -a
# source user's hermes .env if present (silently ignore)
source /c/Users/jespe/AppData/Local/hermes/.env >/dev/null 2>&1 || true
set +a
export PYTHONPATH="/c/Users/jespe/ratking:$PYTHONPATH"
# Disable optional features for a minimal run
export FEATURE_RECAP=false
export FEATURE_HEALTH=false
export FEATURE_READY_CHECK=false
python -u bot_minimal.py
