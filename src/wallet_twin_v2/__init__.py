"""Corporate Wallet Digital Twin V2 production-reference package.

V2 does not import or execute the V1 modelling runtime. V1 artefacts are used
only as frozen non-production fixtures and transparent regression baselines.
"""

from .api import app

__all__ = ["app"]
__version__ = "2.0.0"
