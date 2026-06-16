// SPDX-FileCopyrightText: Copyright (c) 2024–2026, NVIDIA CORPORATION & AFFILIATES. All rights reserved.
// SPDX-License-Identifier: BSD-2-Clause

import { Cpu, Info, Route } from "lucide-react";
import { useState } from "react";
import { techTips, voiceFlowSteps } from "./techTips";

interface TechnologyTipsProps {
  compact?: boolean;
  showFlow?: boolean;
}

export function TechnologyTips({ compact = false, showFlow = false }: TechnologyTipsProps) {
  const [activeTipId, setActiveTipId] = useState<string>("");
  const activeTip = techTips.find((tip) => tip.id === activeTipId);

  return (
    <section className={compact ? "tech-tips tech-tips--compact" : "tech-tips"} aria-label="NVIDIA technology tips">
      <div className="tech-tips__header">
        <div className="tech-tips__title">
          <Cpu size={18} />
          <span>NVIDIA technology stack</span>
        </div>
        <p>High-level demo architecture only. No keys, endpoints, or account details are shown.</p>
      </div>
      <div className="tech-tips__chips">
        {techTips.map((tip) => (
          <button
            key={tip.id}
            type="button"
            className={activeTipId === tip.id ? "tech-tip tech-tip--active" : "tech-tip"}
            aria-expanded={activeTipId === tip.id}
            onClick={() => setActiveTipId((current) => current === tip.id ? "" : tip.id)}
          >
            <Info size={14} />
            {tip.label}
          </button>
        ))}
      </div>
      {activeTip && (
        <div className="tech-tip-panel" role="status">
          <strong>{activeTip.title}</strong>
          <span>{activeTip.description}</span>
        </div>
      )}
      {showFlow && (
        <div className="tech-flow" aria-label="Voice agent pipeline">
          <div className="tech-flow__label">
            <Route size={16} />
            Voice flow
          </div>
          <div className="tech-flow__steps">
            {voiceFlowSteps.map((step) => (
              <span key={step}>{step}</span>
            ))}
          </div>
        </div>
      )}
    </section>
  );
}
