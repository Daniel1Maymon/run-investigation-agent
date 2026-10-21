"""Run the eval from the terminal: every case, every model, a few attempts each,
then write the results table (TEST_PLAN cases 67-68, docs/decisions/0011).
The /eval page runs the same code.

    uv run --env-file .env python -m evals.run_eval [attempts] [model ...]
"""
import sys

from app import config, evaluation, models


def main(attempts: int, model_names: list[str], make_model=models.make_model) -> list[evaluation.Attempt]:
    # `make_model` lets tests pass fake models.
    results = []
    for case in evaluation.load_cases():
        for name in model_names:
            for i in range(attempts):
                # A failed model call comes back as status "error", not an exception (case 66).
                attempt = evaluation.run_attempt(case=case, model=make_model(name=name))
                c = attempt.checks
                print(f"{case.id}  {name}  #{i + 1}: {attempt.status}  outcome={c.outcome} "
                      f"cited={c.cited} cause={c.cause}  {attempt.seconds}s")
                results.append(attempt)
    return results


if __name__ == "__main__":
    n = int(sys.argv[1]) if len(sys.argv) > 1 else config.EVAL_ATTEMPTS
    names = sys.argv[2:] or config.EVAL_MODELS
    done = main(attempts=n, model_names=names)
    if done:
        print(f"written {evaluation.write_results(attempts=done)}")
