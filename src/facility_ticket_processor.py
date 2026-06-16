# SPDX-FileCopyrightText: Copyright (c) 2024-2026, NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: BSD-2-Clause

"""Pipecat processor that turns facility ticket markers into spoken confirmations."""

from __future__ import annotations

from loguru import logger
from pipecat.frames.frames import (
    Frame,
    LLMFullResponseEndFrame,
    LLMFullResponseStartFrame,
    LLMTextFrame,
)
from pipecat.processors.frame_processor import FrameDirection, FrameProcessor
from pipecat.processors.frameworks.rtvi import RTVIServerMessageFrame

from src.facility_ticket_marker import FACILITY_TICKET_MARKER_PREFIX, create_ticket_from_marker
from src.facility_tickets import FacilityTicketStore, TicketValidationError


class FacilityTicketMarkerProcessor(FrameProcessor):
    """Intercepts strict ticket markers emitted by the LLM before TTS."""

    def __init__(self, store: FacilityTicketStore, **kwargs) -> None:
        super().__init__(**kwargs)
        self._store = store
        self._buffer = ""
        self._buffering_marker = False

    async def process_frame(self, frame: Frame, direction: FrameDirection) -> None:
        """Process LLM text frames and replace ticket markers with confirmations."""
        await super().process_frame(frame, direction)

        if isinstance(frame, LLMFullResponseStartFrame):
            self._reset()
            await self.push_frame(frame, direction)
            return

        if isinstance(frame, LLMTextFrame):
            await self._process_text_frame(frame, direction)
            return

        if isinstance(frame, LLMFullResponseEndFrame):
            await self._flush_marker_buffer(direction)
            await self.push_frame(frame, direction)
            return

        await self.push_frame(frame, direction)

    async def _process_text_frame(self, frame: LLMTextFrame, direction: FrameDirection) -> None:
        candidate = self._buffer + frame.text

        if self._buffering_marker or _could_be_marker(candidate):
            self._buffer = candidate
            self._buffering_marker = True
            return

        if self._buffer:
            await self.push_frame(LLMTextFrame(self._buffer), direction)
            self._reset()

        await self.push_frame(frame, direction)

    async def _flush_marker_buffer(self, direction: FrameDirection) -> None:
        if not self._buffer:
            return

        if not self._buffer.lstrip().startswith(FACILITY_TICKET_MARKER_PREFIX):
            await self.push_frame(LLMTextFrame(self._buffer), direction)
            self._reset()
            return

        try:
            result = create_ticket_from_marker(self._buffer, self._store)
        except TicketValidationError as exc:
            logger.warning(f"Could not create facility ticket from LLM marker: {exc}")
            await self.push_frame(
                LLMTextFrame("I could not create the ticket because the details were incomplete. Please repeat it."),
                direction,
            )
        else:
            if result is None:
                await self.push_frame(LLMTextFrame(self._buffer), direction)
            else:
                await self.push_frame(LLMTextFrame(result.speech_text), direction)
                await self.push_frame(
                    RTVIServerMessageFrame(
                        data={
                            "type": "facility_ticket_created",
                            "ticket_id": result.ticket.ticket_id,
                            "status": result.ticket.status,
                            "category": result.ticket.category,
                            "urgency": result.ticket.urgency,
                        }
                    ),
                    direction,
                )
                logger.info(f"Created facility ticket from voice marker: {result.ticket.ticket_id}")
        finally:
            self._reset()

    def _reset(self) -> None:
        self._buffer = ""
        self._buffering_marker = False


def _could_be_marker(text: str) -> bool:
    stripped = text.lstrip()
    return FACILITY_TICKET_MARKER_PREFIX.startswith(stripped) or stripped.startswith(FACILITY_TICKET_MARKER_PREFIX)
