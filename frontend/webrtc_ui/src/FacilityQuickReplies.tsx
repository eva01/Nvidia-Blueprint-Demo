// SPDX-FileCopyrightText: Copyright (c) 2024–2026, NVIDIA CORPORATION & AFFILIATES. All rights reserved.
// SPDX-License-Identifier: BSD-2-Clause

import { buildUserReply, getQuickReplyPrompt } from "./quickReplies";

interface Props {
  latestBotText: string;
  disabled?: boolean;
  onSend: (text: string) => void;
}

export function FacilityQuickReplies({ latestBotText, disabled = false, onSend }: Props) {
  const prompt = getQuickReplyPrompt(latestBotText);

  if (!prompt) return null;

  return (
    <div className="border-t border-gray-200 px-5 py-3 bg-white">
      <div className="text-xs font-semibold uppercase text-gray-500 mb-2">
        {prompt.title}
      </div>
      <div className="flex flex-wrap gap-2">
        {prompt.options.map((option) => (
          <button
            key={`${prompt.kind}-${option.value}`}
            type="button"
            disabled={disabled}
            onClick={() => onSend(buildUserReply(prompt.kind, option.value))}
            className="px-3 py-2 rounded-md border border-gray-300 bg-gray-50 text-sm font-medium text-gray-800 hover:border-nvidia hover:bg-lime-50 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {option.label}
          </button>
        ))}
      </div>
    </div>
  );
}
