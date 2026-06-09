"""Recap worker daemon

Behavior:
- Periodically calls features.cs2_recap.process_queue.process_one()
- If DISCORD_RECAP_WEBHOOK is set, POSTs results there (simple webhook);
  otherwise writes results to logs and leaves the output files in features/cs2_recap/out.

Run: source hermes .env then python -u scripts/recap_worker_daemon.py
"""
import os
import time
import logging
import requests

from features.cs2_recap.process_queue import process_one

LOG = logging.getLogger('recap_worker')
LOG.setLevel(logging.INFO)
handler = logging.StreamHandler()
handler.setFormatter(logging.Formatter('%(asctime)s %(levelname)s %(message)s'))
LOG.addHandler(handler)

WEBHOOK = os.getenv('DISCORD_RECAP_WEBHOOK')
POLL = float(os.getenv('RECAP_POLL_SECONDS', '10'))

LOG.info('Recap worker starting (webhook=%s, poll=%s)', bool(WEBHOOK), POLL)

try:
    while True:
        try:
            res = process_one()
            if res:
                msg = f"Recap for {res['sharecode']} (requested by {res['user']})\n```\n{res['recap_text']}\n```"
                if WEBHOOK:
                    try:
                        requests.post(WEBHOOK, json={'content': msg}, timeout=10)
                        LOG.info('Posted recap %s to webhook', res['sharecode'])
                    except Exception:
                        LOG.exception('Failed to POST recap to webhook; leaving output on disk')
                else:
                    LOG.info('Processed recap %s; output at %s', res['sharecode'], res['out_path'])
        except Exception:
            LOG.exception('Worker loop exception')
        time.sleep(POLL)
except KeyboardInterrupt:
    LOG.info('Recap worker exiting')
