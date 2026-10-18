"""Save a full copy of one run from the viewer, because OpenClaw deletes old log files.

  uv run python scripts/save_run.py <run_id>           → data/runs/<run_id>.json (real, NOT committed)
  uv run python scripts/save_run.py <run_id> --redact  → tests/fixtures/run_<id8>.json (placeholders, committable)

Needs the tunnel (`dash`). See docs/decisions/0004.
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.adapters import openclaw  # noqa: E402

# Free text: replaced by same-length placeholders, so lengths, previews and paging still behave as real.
TEXT_FIELDS = {"user_text", "reply_text", "session_key", "workspace_dir", "file_path",
               "systemPrompt", "text", "args"}

def redact(v, key=None):
    if isinstance(v, dict):
        return {k: redact(x, k) for k, x in v.items() if k != "raw"}  # raw duplicates blocks
    if isinstance(v, list):
        return [redact(x, key) for x in v]
    if isinstance(v, str) and key in TEXT_FIELDS and not v.startswith("[not recorded:"):
        return "·" * len(v)
    return v

def main(run_id: str, redacted: bool) -> None:
    with openclaw.make_client() as client:
        run = openclaw.fetch_run(client, run_id)
    if redacted:
        run, out = redact(run), ROOT / "tests" / "fixtures" / f"run_{run_id[:8]}.json"
    else:
        out = ROOT / "data" / "runs" / f"{run_id}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(run, ensure_ascii=False, indent=1))
    print(f"saved {out.relative_to(ROOT)}")

if __name__ == "__main__":
    main(sys.argv[1], "--redact" in sys.argv[2:])
