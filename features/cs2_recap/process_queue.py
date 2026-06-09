from pathlib import Path
import json
import uuid
from datetime import datetime
import time
import hashlib
import random

ROOT = Path(__file__).parent
QUEUE_DIR = ROOT / 'queue'
OUT_DIR = ROOT / 'out'
PROCESSED_DIR = ROOT / 'processed'

for d in (QUEUE_DIR, OUT_DIR, PROCESSED_DIR):
    d.mkdir(parents=True, exist_ok=True)


def enqueue(requester: str, sharecode: str) -> str:
    """Enqueue a recap job. Returns job id."""
    job_id = uuid.uuid4().hex
    job = {
        'id': job_id,
        'timestamp': datetime.utcnow().isoformat() + 'Z',
        'requester': requester,
        'sharecode': sharecode,
    }
    path = QUEUE_DIR / f'{job_id}.json'
    with path.open('w', encoding='utf-8') as f:
        json.dump(job, f)
    return job_id


def _list_queue_files():
    files = sorted(QUEUE_DIR.glob('*.json'), key=lambda p: p.stat().st_mtime)
    return files


def _deterministic_recap(share: str) -> str:
    """Generate a deterministic, template-based recap derived from the sharecode.

    This is a deterministic placeholder useful for end-to-end testing: it
    produces human-friendly text seeded from a hash of the sharecode so repeated
    runs produce the same output for the same sharecode.
    """
    seed = int(hashlib.sha256(share.encode('utf-8')).hexdigest()[:16], 16)
    rnd = random.Random(seed)

    maps = ['de_dust2', 'de_inferno', 'de_mirage', 'de_vertigo', 'de_nuke']
    map_played = rnd.choice(maps)
    t_score = rnd.randint(0,16)
    ct_score = rnd.randint(0,16)
    # balance scores for realism
    if abs(t_score - ct_score) > 10:
        ct_score = max(0, min(16, t_score + rnd.randint(-3,3)))

    top_names = ['alex', 'sam', 'maria', 'jin', 'pat', 'leo', 'casey']
    top_player = rnd.choice(top_names)
    rounds = max(1, (t_score + ct_score))

    key_rounds = []
    for i in range(min(5, rounds)):
        r = rnd.randint(1, rounds)
        kicker = rnd.choice(top_names)
        desc = rnd.choice([
            'clutch 1v3', 'ace', 'triple entry', 'defuse under fire', 'knife round highlight'
        ])
        key_rounds.append((r, kicker, desc))

    lines = []
    lines.append(f"Map: {map_played}")
    lines.append(f"Final score: T {t_score} - {ct_score} CT")
    lines.append(f"Top player: {top_player} \u2014 standout performance")
    lines.append("")
    lines.append("Notable rounds:")
    for r, k, d in sorted(key_rounds)[:3]:
        lines.append(f" - Round {r}: {k} \u2014 {d}")
    lines.append("")
    lines.append("Short recap:")
    lines.append(f"A fast-paced match on {map_played}. Final score was T {t_score} - {ct_score} CT. {top_player} performed well and had multiple decisive rounds.")
    lines.append("")
    lines.append("(This is an automated placeholder recap. Replace with real processing when ready.)")
    return '\n'.join(lines)


def process_one() -> dict | None:
    """Process a single queued job. Returns result dict or None if none available.

    For Stage 1 this runs a deterministic template-based recap generator so the
    whole queue -> output flow can be tested end-to-end without external APIs.
    """
    files = _list_queue_files()
    if not files:
        return None
    job_path = files[0]
    try:
        with job_path.open('r', encoding='utf-8') as f:
            job = json.load(f)
    except Exception:
        # if unreadable, move to processed to avoid tight loop
        try:
            job_path.replace(PROCESSED_DIR / job_path.name)
        except Exception:
            pass
        return None

    share = job.get('sharecode')
    requester = job.get('requester')
    recap_text = _deterministic_recap(str(share))

    out_path = OUT_DIR / f"{job['id']}.txt"
    try:
        with out_path.open('w', encoding='utf-8') as f:
            f.write(recap_text)
    except Exception:
        # if writing fails, still move job to processed to avoid blocking
        try:
            job_path.replace(PROCESSED_DIR / job_path.name)
        except Exception:
            pass
        return None

    # move job to processed
    try:
        job_path.replace(PROCESSED_DIR / job_path.name)
    except Exception:
        pass

    return {'sharecode': share, 'user': requester, 'recap_text': recap_text, 'out_path': str(out_path)}
