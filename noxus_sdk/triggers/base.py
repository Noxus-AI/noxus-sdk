"""Authoring base for plugin-provided polling triggers.

The platform owns scheduling, state persistence, and event-to-run routing —
exactly as for built-in polling triggers. A plugin trigger only answers
``poll``: given the config and the state left by the previous poll, return
the new events (plain JSON dicts) and the updated state. It runs inside the
plugin's warm sandboxed worker, invoked over JSON-RPC (``trigger.poll``).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar, Generic, TypeVar, get_args

from noxus_sdk.nodes.base import NodeConfiguration
from noxus_sdk.triggers.schemas import TriggerDefinition

if TYPE_CHECKING:
    from noxus_sdk.plugins.context import RemoteExecutionContext


class TriggerConfiguration(NodeConfiguration):
    """Base configuration class for plugin triggers."""


TriggerConfigType = TypeVar("TriggerConfigType", bound=TriggerConfiguration)


class BasePollingTrigger(Generic[TriggerConfigType]):
    trigger_name: ClassVar[str] = "BasePollingTrigger"
    title: ClassVar[str] = ""
    description: ClassVar[str] = ""
    image: ClassVar[str | None] = None
    integrations: ClassVar[list[str]] = []
    polling_interval: ClassVar[float] = 300.0
    # Event field name -> human-readable type label (see TriggerDefinition).
    outputs: ClassVar[dict[str, str]] = {}

    config_class: type[TriggerConfigType]

    def __init_subclass__(cls) -> None:
        cls.config_class = get_args(cls.__orig_bases__[0])[0]  # type: ignore

    def __init__(self, config: TriggerConfigType) -> None:
        self.config = config

    @classmethod
    def get_config_class(cls) -> type[TriggerConfigType]:
        return cls.config_class

    @classmethod
    def get_definition(cls) -> TriggerDefinition:
        return TriggerDefinition(
            type=cls.trigger_name,
            title=cls.title or cls.trigger_name,
            description=cls.description,
            image=cls.image,
            config=cls.get_config_class().serialize(),
            integrations=list(cls.integrations),
            polling_interval=cls.polling_interval,
            outputs=dict(cls.outputs),
        )

    async def poll(
        self, ctx: RemoteExecutionContext, state: dict
    ) -> tuple[list[dict], dict]:
        """Return (events, new_state). Each event is a JSON-serializable dict
        whose fields become the workflow's trigger inputs."""
        raise NotImplementedError
