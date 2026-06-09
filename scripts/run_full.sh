#!/usr/bin/env bash
set -e
# Run full-featured bot: load DISCORD_BOT_TOKEN from Hermes .env and run bot_clean
cd /c/Users/jespe/ratking
set -a
source /c/Users/jespe/AppData/Local/hermes/.env >/dev/null 2>&1 || true
set +a
export PYTHONPATH="/c/Users/jespe/ratking:$PYTHONPATH"
# Enable optional features for full run
export FEATURE_RECAP=true
export FEATURE_HEALTH=true
export FEATURE_READY_CHECK=true
# Run the main clean bot
python -u bot_clean/main.py
