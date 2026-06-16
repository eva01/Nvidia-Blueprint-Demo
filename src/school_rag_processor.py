# SPDX-FileCopyrightText: Copyright (c) 2024-2026, NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: BSD-2-Clause

"""Pipecat processor that injects school KB context before LLM turns."""

from __future__ import annotations

from pipecat.frames.frames import Frame, LLMMessagesAppendFrame, TranscriptionFrame
from pipecat.processors.frame_processor import FrameDirection, FrameProcessor

from src.school_knowledge_base import SchoolKnowledgeBase

_TICKET_INTAKE_HINTS = (
    "report",
    "broken",
    "leak",
    "not working",
    "air conditioner",
    "hvac",
    "electrical",
    "plumbing",
    "cleaning",
    "urgent",
    "ticket",
)


class SchoolRAGContextProcessor(FrameProcessor):
    """Adds retrieved school knowledge snippets to the LLM context."""

    def __init__(self, knowledge_base: SchoolKnowledgeBase, *, min_score: float = 45, **kwargs) -> None:
        super().__init__(**kwargs)
        self._knowledge_base = knowledge_base
        self._min_score = min_score

    async def process_frame(self, frame: Frame, direction: FrameDirection) -> None:
        """Inject a short retrieval context for knowledge-base questions."""
        await super().process_frame(frame, direction)

        if isinstance(frame, TranscriptionFrame) and not _looks_like_ticket_intake(frame.text):
            context = self._knowledge_base.build_prompt_context(frame.text, min_score=self._min_score)
            if context:
                await self.push_frame(
                    LLMMessagesAppendFrame(
                        messages=[
                            {
                                "role": "system",
                                "content": context,
                            }
                        ],
                        run_llm=False,
                    ),
                    direction,
                )

        await self.push_frame(frame, direction)


def _looks_like_ticket_intake(text: str) -> bool:
    lowered = text.lower()
    return any(hint in lowered for hint in _TICKET_INTAKE_HINTS)
