"""Model adapters. The rest of the app gets a model from make_model() and never
imports a provider's SDK."""
from app import config
from app.models.base import Model, ModelNotConfigured


def make_model() -> Model:
    if config.MODEL_PROVIDER == "openrouter":
        from app.models.openrouter import OpenRouterModel
        return OpenRouterModel(name=config.MODEL)
    if config.MODEL_PROVIDER == "anthropic":
        from app.models.claude import ClaudeModel
        return ClaudeModel(name=config.MODEL)
    raise ModelNotConfigured(
        f"unknown MODEL_PROVIDER {config.MODEL_PROVIDER!r} (supported: openrouter, anthropic)")
