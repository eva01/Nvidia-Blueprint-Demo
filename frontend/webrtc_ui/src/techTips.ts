export type TechTipId =
  | "nim"
  | "riva-asr"
  | "riva-tts"
  | "pipecat"
  | "sqlite"
  | "sqlite-vec"
  | "nemotron-embed"
  | "nemotron-rerank";

export interface TechTip {
  id: TechTipId;
  label: string;
  title: string;
  description: string;
}

export const techTips: TechTip[] = [
  {
    id: "nim",
    label: "NIM",
    title: "NVIDIA NIM",
    description: "Serves the LLM through a cloud or self-hosted inference endpoint for real-time ticket intake.",
  },
  {
    id: "riva-asr",
    label: "Riva ASR",
    title: "NVIDIA Riva ASR",
    description: "Turns browser microphone audio into text with NVIDIA speech-to-text services.",
  },
  {
    id: "riva-tts",
    label: "Riva TTS",
    title: "NVIDIA Riva TTS",
    description: "Converts the assistant response into spoken audio with NVIDIA text-to-speech services.",
  },
  {
    id: "pipecat",
    label: "Pipecat",
    title: "Pipecat pipeline",
    description: "Connects WebRTC, ASR, the LLM, ticket creation, and TTS into one real-time voice workflow.",
  },
  {
    id: "sqlite",
    label: "SQLite",
    title: "Local SQLite tickets",
    description: "Stores demo tickets locally so the facility workflow can be shown with simple data sovereignty controls.",
  },
  {
    id: "sqlite-vec",
    label: "sqlite-vec",
    title: "Local vector retrieval",
    description: "Keeps the school knowledge index local while enabling semantic search over configured policy chunks.",
  },
  {
    id: "nemotron-embed",
    label: "Nemotron Embed",
    title: "NVIDIA Nemotron Embed",
    description: "Creates retrieval vectors through a hosted NVIDIA endpoint when the sqlite-vec RAG backend is enabled.",
  },
  {
    id: "nemotron-rerank",
    label: "Nemotron Rerank",
    title: "NVIDIA Nemotron Rerank",
    description: "Optionally rescores retrieved school knowledge chunks before the LLM writes a spoken answer.",
  },
];

export const voiceFlowSteps = [
  "Browser microphone",
  "NVIDIA Riva ASR",
  "NVIDIA NIM LLM",
  "School KB retrieval",
  "Facility ticket marker",
  "SQLite ticket store",
  "NVIDIA Riva TTS",
];

export function getTechTipById(id: TechTipId): TechTip | undefined {
  return techTips.find((tip) => tip.id === id);
}
