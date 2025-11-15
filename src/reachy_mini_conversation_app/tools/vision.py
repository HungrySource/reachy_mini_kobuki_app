"""Vision-related tools."""

import asyncio
import base64
import logging
from typing import Any, Dict

import cv2

from reachy_mini_conversation_app.tools import Tool, ToolDependencies


logger = logging.getLogger(__name__)


class Camera(Tool):
    """Take a picture with the camera and ask a question about it."""

    name = "camera"
    description = "Take a picture with the camera and ask a question about it."
    parameters_schema = {
        "type": "object",
        "properties": {
            "question": {
                "type": "string",
                "description": "The question to ask about the picture",
            },
        },
        "required": ["question"],
    }

    async def __call__(self, deps: ToolDependencies, **kwargs: Any) -> Dict[str, Any]:
        """Take a picture with the camera and ask a question about it."""
        image_query = (kwargs.get("question") or "").strip()
        if not image_query:
            logger.warning("camera: empty question")
            return {"error": "question must be a non-empty string"}

        logger.info("Tool call: camera question=%s", image_query[:120])

        # Get frame from camera worker buffer (like main_works.py)
        if deps.camera_worker is not None:
            frame = deps.camera_worker.get_latest_frame()
            if frame is None:
                logger.error("No frame available from camera worker")
                return {"error": "No frame available"}
        else:
            logger.error("Camera worker not available")
            return {"error": "Camera worker not available"}

        # Use vision manager for processing if available
        if deps.vision_manager is not None:
            vision_result = await asyncio.to_thread(
                deps.vision_manager.processor.process_image, frame, image_query,
            )
            if isinstance(vision_result, dict) and "error" in vision_result:
                return vision_result
            return (
                {"image_description": vision_result}
                if isinstance(vision_result, str)
                else {"error": "vision returned non-string"}
            )
        # Return base64 encoded image like main_works.py camera tool
        temp_path = "/tmp/camera_frame.jpg"
        cv2.imwrite(temp_path, frame)
        with open(temp_path, "rb") as f:
            b64_encoded = base64.b64encode(f.read()).decode("utf-8")
        return {"b64_im": b64_encoded}


class HeadTracking(Tool):
    """Toggle head tracking state."""

    name = "head_tracking"
    description = "Toggle head tracking state."
    parameters_schema = {
        "type": "object",
        "properties": {"start": {"type": "boolean"}},
        "required": ["start"],
    }

    async def __call__(self, deps: ToolDependencies, **kwargs: Any) -> Dict[str, Any]:
        """Enable or disable head tracking."""
        enable = bool(kwargs.get("start"))

        # Update camera worker head tracking state
        if deps.camera_worker is not None:
            deps.camera_worker.set_head_tracking_enabled(enable)

        status = "started" if enable else "stopped"
        logger.info("Tool call: head_tracking %s", status)
        return {"status": f"head tracking {status}"}

