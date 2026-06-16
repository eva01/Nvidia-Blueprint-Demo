"""Local RTVI input extensions for the school facility demo."""

from __future__ import annotations

from typing import Any

from nvidia_pipecat.processors.nvidia_rtvi import NvidiaRTVIInput
from pipecat.frames.frames import LLMMessagesUpdateFrame
from pipecat.processors.frameworks.rtvi import RTVIClientMessage


class FacilityRTVIInput(NvidiaRTVIInput):
    """Adds text/button user replies to NVIDIA's RTVI input processor."""

    async def _handle_custom_client_message(self, msg: RTVIClientMessage):
        if msg.type == "submit_user_text":
            await self._handle_submit_user_text(msg, msg.data)
            return

        await super()._handle_custom_client_message(msg)

    async def _handle_submit_user_text(self, msg: RTVIClientMessage, data: Any):
        text = data.get("text", "") if isinstance(data, dict) else ""
        if not isinstance(text, str) or not text.strip():
            await self.send_error_response(msg, "Missing text")
            return

        messages = self._context.get_messages().copy()
        messages.append({"role": "user", "content": text.strip()})
        await self.push_frame(LLMMessagesUpdateFrame(messages=messages, run_llm=True))
        await self.send_server_response(msg, {"status": "submitted"})
