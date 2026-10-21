"""Every source the pipeline can sync. Each module in this package defines

    SOURCE = Source(code=..., name=..., mock_connector=..., loader=...)

and is found automatically, so adding a source means adding one module here.
"""
import importlib
import pkgutil
from collections.abc import Callable
from dataclasses import dataclass


@dataclass(frozen=True)
class Source:
    code: str  # matches SourceSystem.code, e.g. "smis"
    name: str  # e.g. "School Management Information System"
    mock_connector: type  # takes seed= and scale=
    loader: Callable  # see integrations.pipeline


def all_sources():
    """{code: Source} for every module in this package."""
    sources = {}
    for module in pkgutil.iter_modules(__path__):
        source = getattr(importlib.import_module(f"{__name__}.{module.name}"), "SOURCE", None)
        if source is not None:
            sources[source.code] = source
    return sources
