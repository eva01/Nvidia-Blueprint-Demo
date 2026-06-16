import assert from "node:assert/strict";
import test from "node:test";

import {
  buildUserReply,
  getQuickReplyPrompt,
} from "./quickReplies.ts";

test("shows category chips when the bot asks for category", () => {
  const prompt = getQuickReplyPrompt("What category best describes this issue?");

  assert.equal(prompt?.kind, "category");
  assert.deepEqual(
    prompt?.options.map((option) => option.value),
    ["hvac", "electrical", "plumbing", "it", "furniture", "safety", "cleaning", "other"],
  );
});

test("shows urgency chips when the bot asks for urgency", () => {
  const prompt = getQuickReplyPrompt("How urgent is this issue?");

  assert.equal(prompt?.kind, "urgency");
  assert.deepEqual(
    prompt?.options.map((option) => option.value),
    ["low", "normal", "urgent"],
  );
});

test("does not show chips for free-form questions", () => {
  assert.equal(getQuickReplyPrompt("Who should I list as the reporter?"), null);
  assert.equal(getQuickReplyPrompt("What is the exact location?"), null);
});

test("formats selected values as natural user replies", () => {
  assert.equal(buildUserReply("category", "electrical"), "Category is electrical.");
  assert.equal(buildUserReply("urgency", "urgent"), "Urgency is urgent.");
});
