"""Settings, read from environment variables."""
import os

# The trace viewer's base URL. On the Mac this is the SSH tunnel opened by `dash`.
VIEWER_URL = os.environ.get(key="VIEWER_URL", default="http://127.0.0.1:8765")
# Seconds to wait for the viewer. A closed tunnel should fail fast, not hang.
VIEWER_TIMEOUT = float(os.environ.get(key="VIEWER_TIMEOUT", default="5"))

# The investigator's model. Only the adapter for MODEL_PROVIDER knows its API.
MODEL_PROVIDER = os.environ.get(key="MODEL_PROVIDER", default="openrouter")
# Model names are per provider (OpenRouter: "vendor/model").
DEFAULT_MODELS = {"openrouter": "deepseek/deepseek-v4.1-flash", "anthropic": "claude-opus-5-5"}
MODEL = os.environ.get(key="INVESTIGATOR_MODEL") or DEFAULT_MODELS.get(MODEL_PROVIDER, "")
# Hard limits for one investigation (docs/decisions/0005).
MAX_STEPS = int(os.environ.get(key="INVESTIGATOR_MAX_STEPS", default="12"))        # model calls
MAX_SECONDS = float(os.environ.get(key="INVESTIGATOR_MAX_SECONDS", default="180"))
# The investigation log (docs/decisions/0007): INFO = one line per step,
# DEBUG = also the model's thinking and words.
LOG_LEVEL = os.environ.get(key="LOG_LEVEL", default="INFO").upper()
