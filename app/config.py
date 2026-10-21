"""Settings, read from environment variables."""
import os
from pathlib import Path

# The trace viewer's base URL. On the Mac this is the SSH tunnel opened by `dash`.
VIEWER_URL = os.environ.get("VIEWER_URL", "http://127.0.0.1:8765")
# Seconds to wait for the viewer. A closed tunnel should fail fast, not hang.
VIEWER_TIMEOUT = float(os.environ.get("VIEWER_TIMEOUT", "5"))

# The investigator's model. Only the adapter for MODEL_PROVIDER knows its API.
MODEL_PROVIDER = os.environ.get("MODEL_PROVIDER", "openrouter")
# Model names are per provider (OpenRouter: "vendor/model").
DEFAULT_MODELS = {"openrouter": "deepseek/deepseek-v4.1-flash", "anthropic": "claude-opus-5-5"}
MODEL = os.environ.get("INVESTIGATOR_MODEL") or DEFAULT_MODELS.get(MODEL_PROVIDER, "")
# Hard limits for one investigation (docs/decisions/0005).
MAX_STEPS = int(os.environ.get("INVESTIGATOR_MAX_STEPS", "12"))        # model calls
MAX_SECONDS = float(os.environ.get("INVESTIGATOR_MAX_SECONDS", "180"))
# The investigation log (docs/decisions/0007): INFO = one line per step,
# DEBUG = also the model's thinking and words.
LOG_LEVEL = os.environ.get("LOG_LEVEL", "INFO").upper()

# The evaluation (docs/decisions/0011). The cases are committed; the saved
# copies of the runs hold personal content, so they live in git-ignored data/.
ROOT = Path(__file__).resolve().parent.parent
EVAL_CASES = ROOT / "evals" / "cases.json"
EVAL_RUNS_DIR = ROOT / "data" / "eval-runs"
EVAL_RESULTS_DIR = ROOT / "evals" / "results"
# The cheap models the eval compares, and how many attempts each gets.
EVAL_MODELS = ["deepseek/deepseek-v4.1-flash", "qwen/qwen3.7-flash", "z-ai/glm-5.3-flash"]
EVAL_ATTEMPTS = 3
