"""Plugin sources for different origins"""

from typing import Annotated

from pydantic import Field

from noxus_sdk.plugins.sources.git import GitPluginSource
from noxus_sdk.plugins.sources.local import LocalPluginSource
from noxus_sdk.plugins.sources.marketplace import MarketplacePluginSource
from noxus_sdk.plugins.sources.upload import UploadPluginSource

AnyPluginSource = Annotated[
    GitPluginSource | LocalPluginSource | UploadPluginSource | MarketplacePluginSource,
    Field(discriminator="type"),
]

__all__ = [
    "AnyPluginSource",
    "GitPluginSource",
    "LocalPluginSource",
    "MarketplacePluginSource",
    "UploadPluginSource",
]
