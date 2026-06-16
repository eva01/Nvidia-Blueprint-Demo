import assert from "node:assert/strict";
import { test } from "node:test";

test("resolveRtcOfferUrl uses explicit backend port", async () => {
  globalThis.window = { location: { hostname: "127.0.0.1" } } as Window & typeof globalThis;
  const { resolveRtcOfferUrl } = await import("./config.ts");

  assert.equal(resolveRtcOfferUrl("8787", "127.0.0.1"), "http://127.0.0.1:8787/offer");
});

test("resolveRtcOfferUrl defaults to 7860", async () => {
  globalThis.window = { location: { hostname: "localhost" } } as Window & typeof globalThis;
  const { resolveRtcOfferUrl } = await import("./config.ts");

  assert.equal(resolveRtcOfferUrl("", "localhost"), "http://localhost:7860/offer");
});

test("resolveFacilityApiUrl resolves backend facility paths", async () => {
  globalThis.window = { location: { hostname: "operator.local" } } as Window & typeof globalThis;
  const { resolveFacilityApiUrl } = await import("./config.ts");

  assert.equal(
    resolveFacilityApiUrl("/facility/tickets", "8787", "operator.local"),
    "http://operator.local:8787/facility/tickets"
  );
});
