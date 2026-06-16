// SPDX-FileCopyrightText: Copyright (c) 2024–2026, NVIDIA CORPORATION & AFFILIATES. All rights reserved.
// SPDX-License-Identifier: BSD-2-Clause

export const RTC_CONFIG = {};

const host = window.location.hostname;

export function resolveRtcOfferUrl(port: string | undefined, hostname = host): string {
  const backendPort = port?.trim() || "7860";
  return `http://${hostname}:${backendPort}/offer`;
}

export function resolveFacilityApiUrl(path: string, port: string | undefined, hostname = host): string {
  const backendPort = port?.trim() || "7860";
  const normalizedPath = path.startsWith("/") ? path : `/${path}`;
  return `http://${hostname}:${backendPort}${normalizedPath}`;
}

export function resolveFacilityApiBaseUrl(port: string | undefined, hostname = host): string {
  const backendPort = port?.trim() || "7860";
  return `http://${hostname}:${backendPort}`;
}

const viteEnv = (import.meta as ImportMeta & { env?: { VITE_VOICE_BACKEND_PORT?: string } }).env;

export const RTC_OFFER_URL = resolveRtcOfferUrl(viteEnv?.VITE_VOICE_BACKEND_PORT);
export const FACILITY_API_BASE_URL = resolveFacilityApiBaseUrl(viteEnv?.VITE_VOICE_BACKEND_PORT);
