"""Provider factory and exports."""

from __future__ import annotations

from typing import Any, Optional

from runner.hermeticity.modes import HermeticityPolicy
from runner.providers.base import ExecutionProvider, ProviderError
from runner.providers.local_fake import LocalFakeProvider
from runner.providers.morph import MorphCloudProvider


def get_provider(
    name: str,
    *,
    root: Optional[str] = None,
    hermeticity: Optional[HermeticityPolicy] = None,
    **kwargs: Any,
) -> ExecutionProvider:
    if name in {"local-fake", "local_fake", "fake"}:
        if root is None:
            raise ProviderError("local-fake provider requires root=")
        return LocalFakeProvider(root, hermeticity=hermeticity, **kwargs)
    if name in {"morph", "morphcloud"}:
        return MorphCloudProvider(hermeticity=hermeticity, **kwargs)
    raise ProviderError(f"unknown provider: {name}")


__all__ = [
    "ExecutionProvider",
    "LocalFakeProvider",
    "MorphCloudProvider",
    "ProviderError",
    "get_provider",
]
