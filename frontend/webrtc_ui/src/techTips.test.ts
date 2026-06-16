import assert from "node:assert/strict";
import { test } from "node:test";

import { getTechTipById, techTips, voiceFlowSteps } from "./techTips.ts";

test("tech tips explain the NVIDIA voice stack and local storage", () => {
  assert.deepEqual(
    techTips.map((tip) => tip.id),
    ["nim", "riva-asr", "riva-tts", "pipecat", "sqlite", "sqlite-vec", "nemotron-embed", "nemotron-rerank"],
  );
  assert.match(getTechTipById("nim")?.description ?? "", /inference/i);
  assert.match(getTechTipById("riva-asr")?.description ?? "", /speech-to-text/i);
  assert.match(getTechTipById("riva-tts")?.description ?? "", /text-to-speech/i);
  assert.match(getTechTipById("sqlite-vec")?.description ?? "", /semantic search/i);
  assert.match(getTechTipById("nemotron-embed")?.description ?? "", /hosted NVIDIA endpoint/i);
  assert.doesNotMatch(JSON.stringify(techTips), /next version|Nemotron Parse|automatic PDF/i);
});

test("voice flow steps describe the demo pipeline without secrets", () => {
  assert.deepEqual(voiceFlowSteps, [
    "Browser microphone",
    "NVIDIA Riva ASR",
    "NVIDIA NIM LLM",
    "School KB retrieval",
    "Facility ticket marker",
    "SQLite ticket store",
    "NVIDIA Riva TTS",
  ]);

  assert.doesNotMatch(JSON.stringify(techTips), /nvapi-|api key|token/i);
});
