// SPDX-FileCopyrightText: Copyright (c) 2024–2026, NVIDIA CORPORATION & AFFILIATES. All rights reserved.
// SPDX-License-Identifier: BSD-2-Clause

export type TicketStatus = "open" | "in_progress" | "resolved";

export interface FacilityTicket {
  ticket_id: string;
  status: TicketStatus;
  category: string;
  location: string;
  summary: string;
  urgency: "low" | "normal" | "urgent";
  reporter: string;
  transcript_snippet: string;
  sensitivity: string;
  redaction_applied: boolean;
  created_at: string;
  updated_at: string;
}

export type FacilityTicketUpdate = Partial<
  Pick<
    FacilityTicket,
    "status" | "category" | "location" | "summary" | "urgency" | "reporter" | "transcript_snippet"
  >
>;

export interface FacilitySummary {
  total_tickets: number;
  open_tickets: number;
  status_counts: Record<TicketStatus, number>;
  category_counts: Record<string, number>;
  urgency_counts: Record<string, number>;
  redacted_tickets: number;
  audit_events: number;
  last_ticket_id: string | null;
  sovereignty?: {
    mode: string;
    data_residency_region: string;
    storage_backend: string;
    pii_redaction_enabled: boolean;
    audit_log_enabled: boolean;
  };
}

type Fetcher = typeof fetch;

export function formatTicketStatus(status: TicketStatus): string {
  if (status === "in_progress") return "In progress";
  if (status === "resolved") return "Closed";
  return "Open";
}

export function formatTicketUrgency(urgency: FacilityTicket["urgency"]): string {
  return urgency.charAt(0).toUpperCase() + urgency.slice(1);
}

export async function fetchFacilityTickets(
  apiBaseUrl: string,
  fetchImpl: Fetcher = fetch
): Promise<FacilityTicket[]> {
  return requestJson<FacilityTicket[]>(`${apiBaseUrl}/facility/tickets`, undefined, fetchImpl);
}

export async function fetchFacilitySummary(
  apiBaseUrl: string,
  fetchImpl: Fetcher = fetch
): Promise<FacilitySummary> {
  return requestJson<FacilitySummary>(`${apiBaseUrl}/facility/summary`, undefined, fetchImpl);
}

export async function updateFacilityTicketStatus(
  ticketId: string,
  status: TicketStatus,
  apiBaseUrl: string,
  fetchImpl: Fetcher = fetch
): Promise<FacilityTicket> {
  return requestJson<FacilityTicket>(
    `${apiBaseUrl}/facility/tickets/${encodeURIComponent(ticketId)}/status`,
    {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ status }),
    },
    fetchImpl
  );
}

export async function updateFacilityTicket(
  ticketId: string,
  ticket: FacilityTicketUpdate,
  apiBaseUrl: string,
  fetchImpl: Fetcher = fetch
): Promise<FacilityTicket> {
  return requestJson<FacilityTicket>(
    `${apiBaseUrl}/facility/tickets/${encodeURIComponent(ticketId)}`,
    {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(ticket),
    },
    fetchImpl
  );
}

export async function deleteFacilityTicket(
  ticketId: string,
  apiBaseUrl: string,
  fetchImpl: Fetcher = fetch
): Promise<{ ticket_id: string; deleted: boolean }> {
  return requestJson<{ ticket_id: string; deleted: boolean }>(
    `${apiBaseUrl}/facility/tickets/${encodeURIComponent(ticketId)}`,
    {
      method: "DELETE",
    },
    fetchImpl
  );
}

async function requestJson<T>(
  url: string,
  init: RequestInit | undefined,
  fetchImpl: Fetcher
): Promise<T> {
  const response = await fetchImpl(url, init);
  if (!response.ok) {
    let detail = `HTTP ${response.status}`;
    try {
      const body = (await response.json()) as { detail?: string };
      if (body.detail) detail = body.detail;
    } catch {
      // Keep the status-only fallback when the backend response is not JSON.
    }
    throw new Error(detail);
  }
  return response.json() as Promise<T>;
}
