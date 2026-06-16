# SPDX-FileCopyrightText: Copyright (c) 2024-2026, NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: BSD-2-Clause

"""Safety guard processor for LLM output."""

from __future__ import annotations

from typing import Protocol

from loguru import logger
from pipecat.frames.frames import Frame, LLMFullResponseEndFrame, LLMFullResponseStartFrame, LLMTextFrame
from pipecat.processors.frame_processor import FrameDirection, FrameProcessor


class SafetyGuard(Protocol):
    """Checks whether generated text is safe to speak."""

    def is_safe(self, text: str) -> bool:
        """Return true when text can be spoken to the user."""


class SafetyGuardProcessor(FrameProcessor):
    """Buffers an LLM response and replaces unsafe output before TTS."""

    def __init__(
        self,
        guard: SafetyGuard,
        *,
        fallback_text: str = "I cannot help with that request. Please ask about school facility support.",
        **kwargs,
    ) -> None:
        super().__init__(**kwargs)
        self._guard = guard
        self._fallback_text = fallback_text
        self._buffer = ""

    async def process_frame(self, frame: Frame, direction: FrameDirection) -> None:
        """Apply a safety check to complete LLM text responses."""
        await super().process_frame(frame, direction)

        if isinstance(frame, LLMFullResponseStartFrame):
            self._buffer = ""
            await self.push_frame(frame, direction)
            return

        if isinstance(frame, LLMTextFrame):
            self._buffer += frame.text
            return

        if isinstance(frame, LLMFullResponseEndFrame):
            if self._buffer:
                try:
                    is_safe = self._guard.is_safe(self._buffer)
                except Exception as exc:
                    logger.warning(f"Safety guard check failed; allowing response for demo continuity: {exc}")
                    is_safe = True
                text = self._buffer if is_safe else self._fallback_text
                await self.push_frame(LLMTextFrame(text), direction)
            self._buffer = ""
            await self.push_frame(frame, direction)
            return

        await self.push_frame(frame, direction)
