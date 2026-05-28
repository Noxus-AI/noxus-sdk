from pydantic import BaseModel, Field
from typing import Literal, Annotated


class BaseDetailsDisplay(BaseModel):
    """Base class for all detail displays."""

    type: str = "base"
    label: str
    description: str | None = None
    col_span: int = 12  # Grid layout (1-12)
    collapsible: bool = False
    default_collapsed: bool = False


class DetailsExecutionProgress(BaseDetailsDisplay):
    """Step-by-step execution progress with screenshots and status."""

    type: Literal["execution_progress"] = "execution_progress"  # type: ignore
    has_screenshots: bool = True
    has_extracted_data: bool = True
    show_slideshow_button: bool = True
    enable_step_expansion: bool = True


class DetailsJSONViewer(BaseDetailsDisplay):
    """Structured JSON display with syntax highlighting."""

    type: Literal["json_viewer"] = "json_viewer"  # type: ignore
    enable_search: bool = True
    enable_copy: bool = True
    max_depth: int | None = None
    syntax_theme: Literal["light", "dark", "auto"] = "auto"


class DetailsChatViewer(BaseDetailsDisplay):
    """Chat message display for agent conversations."""

    type: Literal["chat_viewer"] = "chat_viewer"  # type: ignore
    show_tool_calls: bool = True


# Union type for all displays
AnyDetailsDisplay = Annotated[
    DetailsExecutionProgress | DetailsJSONViewer | DetailsChatViewer,
    Field(discriminator="type"),
]
