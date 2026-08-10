"""Corporate Wallet Digital Twin governed evidence/economics substrate.

The API object is loaded lazily so analytical modules and the additive V3 layer
can import V2 contracts without creating an API/router import cycle.
"""

from typing import Any


__all__ = ["app"]
__version__ = "3.0.0"


def __getattr__(name: str) -> Any:
    if name == "app":
        from .api import app

        return app
    raise AttributeError(name)
