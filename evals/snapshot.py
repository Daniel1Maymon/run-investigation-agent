"""Save a frozen copy of a run for the eval (TEST_PLAN case 61, docs/decisions/0011).

    uv run python -m evals.snapshot <run_id>     # the tunnel must be open (`dash`)
"""
import sys

from app import evaluation
from app.adapters import openclaw


def main(run_ids: list[str]) -> int:
    failed = 0
    with openclaw.make_client() as client:
        for run_id in run_ids:
            try:
                path = evaluation.save_snapshot(client=client, run_id=run_id)
                print(f"saved {path}")
            except (FileExistsError, openclaw.RunNotFound, openclaw.ViewerUnavailable) as ex:
                print(f"not saved: {ex}")
                failed += 1
    return 1 if failed else 0


if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    sys.exit(main(run_ids=sys.argv[1:]))
