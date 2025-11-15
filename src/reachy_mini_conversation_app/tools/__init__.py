"""Tool system for the Reachy Mini conversation app."""

from __future__ import annotations
import abc
import json
import inspect
import logging
from typing import Any, Dict, List, Literal
from dataclasses import dataclass

from reachy_mini import ReachyMini


logger = logging.getLogger(__name__)


def get_concrete_subclasses(base: type[Tool]) -> List[type[Tool]]:
    """Recursively find all concrete (non-abstract) subclasses of a base class."""
    result: List[type[Tool]] = []
    for cls in base.__subclasses__():
        if not inspect.isabstract(cls):
            result.append(cls)
        # recurse into subclasses
        result.extend(get_concrete_subclasses(cls))
    return result


# Types & state
Direction = Literal["left", "right", "up", "down", "front"]


@dataclass
class ToolDependencies:
    """External dependencies injected into tools."""

    reachy_mini: ReachyMini
    movement_manager: Any  # MovementManager from moves.py
    # Optional deps
    camera_worker: Any | None = None  # CameraWorker for frame buffering
    vision_manager: Any | None = None
    head_wobbler: Any | None = None  # HeadWobbler for audio-reactive motion
    motion_duration_s: float = 1.0


# Tool base class
class Tool(abc.ABC):
    """Base abstraction for tools used in function-calling.

    Each tool must define:
      - name: str
      - description: str
      - parameters_schema: Dict[str, Any]  # JSON Schema
    """

    name: str
    description: str
    parameters_schema: Dict[str, Any]

    def spec(self) -> Dict[str, Any]:
        """Return the function spec for LLM consumption."""
        return {
            "type": "function",
            "name": self.name,
            "description": self.description,
            "parameters": self.parameters_schema,
        }

    @abc.abstractmethod
    async def __call__(self, deps: ToolDependencies, **kwargs: Any) -> Dict[str, Any]:
        """Async tool execution entrypoint."""
        raise NotImplementedError


# Import all tool implementations to register them with the Tool base class
# This must happen after Tool is defined but before get_concrete_subclasses is called
# Import directly from submodules to avoid circular imports
from reachy_mini_conversation_app.tools.movement import MoveHead  # noqa: E402
from reachy_mini_conversation_app.tools.vision import Camera, HeadTracking  # noqa: E402
from reachy_mini_conversation_app.tools.dance import Dance, StopDance  # noqa: E402
from reachy_mini_conversation_app.tools.emotion import PlayEmotion, StopEmotion  # noqa: E402
from reachy_mini_conversation_app.tools.do_nothing import DoNothing  # noqa: E402


# Registry & specs (dynamic)

# List of available tool classes
ALL_TOOLS: Dict[str, Tool] = {cls.name: cls() for cls in get_concrete_subclasses(Tool)}  # type: ignore[type-abstract]
ALL_TOOL_SPECS = [tool.spec() for tool in ALL_TOOLS.values()]


# Dispatcher
def _safe_load_obj(args_json: str) -> Dict[str, Any]:
    try:
        parsed_args = json.loads(args_json or "{}")
        return parsed_args if isinstance(parsed_args, dict) else {}
    except Exception:
        logger.warning("bad args_json=%r", args_json)
        return {}


async def dispatch_tool_call(tool_name: str, args_json: str, deps: ToolDependencies) -> Dict[str, Any]:
    """Dispatch a tool call by name with JSON args and dependencies."""
    tool = ALL_TOOLS.get(tool_name)

    if not tool:
        return {"error": f"unknown tool: {tool_name}"}

    args = _safe_load_obj(args_json)
    try:
        return await tool(deps, **args)
    except Exception as e:
        msg = f"{type(e).__name__}: {e}"
        logger.exception("Tool error in %s: %s", tool_name, msg)
        return {"error": msg}


__all__ = [
    # Base classes and types
    "Tool",
    "ToolDependencies",
    "Direction",
    # Tool implementations
    "MoveHead",
    "Camera",
    "HeadTracking",
    "Dance",
    "StopDance",
    "PlayEmotion",
    "StopEmotion",
    "DoNothing",
    # Registry and dispatcher
    "ALL_TOOLS",
    "ALL_TOOL_SPECS",
    "dispatch_tool_call",
]

