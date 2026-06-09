# Hermes-playground

Run variants
------------

This repository includes two convenience scripts to run the bot in two different configurations:

- scripts/run_minimal.sh
  - Loads DISCORD_BOT_TOKEN from your Hermes .env (C:\Users\jespe\AppData\Local\hermes\.env) if present.
  - Disables optional features and runs the minimal bot entrypoint.
  - Usage: ./scripts/run_minimal.sh

- scripts/run_full.sh
  - Loads DISCORD_BOT_TOKEN from your Hermes .env (C:\Users\jespe\AppData\Local\hermes\.env) if present.
  - Enables FEATURE_RECAP, FEATURE_HEALTH, and FEATURE_READY_CHECK and runs the full bot.
  - Usage: ./scripts/run_full.sh

Both scripts ensure the repository root is on PYTHONPATH so the local packages are used.

Test helper
-----------

A simple test script is included to validate the commands loader: tests/test_commands_loader.py
Run it with:

python tests/test_commands_loader.py

It will print a short confirmation message and exit non-zero on failure.
