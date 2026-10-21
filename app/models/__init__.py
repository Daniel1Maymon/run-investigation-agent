"""Model adapters. The rest of the app gets a model from make_model() and never
imports a provider's SDK."""
from app import config
from app.models.base import Model, ModelNotConfigured


def make_model(name: str | None = None) -> Model:
    # `name` picks a model other than the configured one (the eval compares several).
    name = name or config.MODEL
    if config.MODEL_PROVIDER == "openrouter":
        from app.models.openrouter import OpenRouterModel
        return OpenRouterModel(name=name)
    if config.MODEL_PROVIDER == "anthropic":
        from app.models.claude import ClaudeModel
        return ClaudeModel(name=name)
    raise ModelNotConfigured(
        f"unknown MODEL_PROVIDER {config.MODEL_PROVIDER!r} (supported: openrouter, anthropic)")
