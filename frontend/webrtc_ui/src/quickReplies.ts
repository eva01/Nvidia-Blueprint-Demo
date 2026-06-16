export type QuickReplyKind = "category" | "urgency" | "confirmation";

export interface QuickReplyOption {
  label: string;
  value: string;
}

export interface QuickReplyPrompt {
  kind: QuickReplyKind;
  title: string;
  options: QuickReplyOption[];
}

const CATEGORY_OPTIONS: QuickReplyOption[] = [
  { label: "HVAC", value: "hvac" },
  { label: "Electrical", value: "electrical" },
  { label: "Plumbing", value: "plumbing" },
  { label: "IT", value: "it" },
  { label: "Furniture", value: "furniture" },
  { label: "Safety", value: "safety" },
  { label: "Cleaning", value: "cleaning" },
  { label: "Other", value: "other" },
];

const URGENCY_OPTIONS: QuickReplyOption[] = [
  { label: "Low", value: "low" },
  { label: "Normal", value: "normal" },
  { label: "Urgent", value: "urgent" },
];

const CONFIRMATION_OPTIONS: QuickReplyOption[] = [
  { label: "Yes", value: "yes" },
  { label: "No", value: "no" },
];

export function getQuickReplyPrompt(botText: string | null | undefined): QuickReplyPrompt | null {
  const normalized = (botText ?? "").toLowerCase();

  if (normalized.includes("category")) {
    return {
      kind: "category",
      title: "Choose category",
      options: CATEGORY_OPTIONS,
    };
  }

  if (normalized.includes("urgent") || normalized.includes("urgency")) {
    return {
      kind: "urgency",
      title: "Choose urgency",
      options: URGENCY_OPTIONS,
    };
  }

  if (
    normalized.includes("is that correct") ||
    normalized.includes("should i create") ||
    normalized.includes("should i submit") ||
    normalized.includes("should i mark") ||
    normalized.includes("confirm")
  ) {
    return {
      kind: "confirmation",
      title: "Confirm",
      options: CONFIRMATION_OPTIONS,
    };
  }

  return null;
}

export function buildUserReply(kind: QuickReplyKind, value: string): string {
  if (kind === "category") return `Category is ${value}.`;
  if (kind === "urgency") return `Urgency is ${value}.`;
  return value === "yes" ? "Yes, that is correct." : "No.";
}
