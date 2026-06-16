// SPDX-FileCopyrightText: Copyright (c) 2024–2026, NVIDIA CORPORATION & AFFILIATES. All rights reserved.
// SPDX-License-Identifier: BSD-2-Clause

import { AlertCircle, CheckCircle2, Loader2, Mic, Pencil, RefreshCw, Save, Trash2, X } from "lucide-react";
import { useCallback, useEffect, useMemo, useState } from "react";
import { toast } from "sonner";
import { FACILITY_API_BASE_URL } from "./config";
import { TechnologyTips } from "./TechnologyTips";
import {
  fetchFacilitySummary,
  fetchFacilityTickets,
  formatTicketStatus,
  formatTicketUrgency,
  deleteFacilityTicket,
  updateFacilityTicket,
  updateFacilityTicketStatus,
  type FacilityTicketUpdate,
  type FacilitySummary,
  type FacilityTicket,
  type TicketStatus,
} from "./facilityTickets";

type StatusFilter = "all" | TicketStatus;

interface FacilityDashboardProps {
  onStartVoice: () => void;
}

const statusFilters: Array<{ label: string; value: StatusFilter }> = [
  { label: "All", value: "all" },
  { label: "Open", value: "open" },
  { label: "In progress", value: "in_progress" },
  { label: "Closed", value: "resolved" },
];

const categories = ["hvac", "electrical", "plumbing", "it", "furniture", "safety", "cleaning", "other"];
const urgencies: Array<FacilityTicket["urgency"]> = ["low", "normal", "urgent"];
const statuses: TicketStatus[] = ["open", "in_progress", "resolved"];

export function FacilityDashboard({ onStartVoice }: FacilityDashboardProps) {
  const [tickets, setTickets] = useState<FacilityTicket[]>([]);
  const [summary, setSummary] = useState<FacilitySummary | null>(null);
  const [statusFilter, setStatusFilter] = useState<StatusFilter>("all");
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string>("");
  const [updatingTicketId, setUpdatingTicketId] = useState<string>("");
  const [editingTicket, setEditingTicket] = useState<FacilityTicket | null>(null);
  const [deletingTicketId, setDeletingTicketId] = useState<string>("");

  const loadTickets = useCallback(async (mode: "initial" | "refresh" = "refresh") => {
    if (mode === "initial") setLoading(true);
    else setRefreshing(true);
    setError("");
    try {
      const [nextTickets, nextSummary] = await Promise.all([
        fetchFacilityTickets(FACILITY_API_BASE_URL),
        fetchFacilitySummary(FACILITY_API_BASE_URL),
      ]);
      setTickets(nextTickets);
      setSummary(nextSummary);
    } catch (err) {
      const message = err instanceof Error ? err.message : "Failed to load tickets";
      setError(message);
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, []);

  useEffect(() => {
    void loadTickets("initial");
  }, [loadTickets]);

  const filteredTickets = useMemo(() => {
    if (statusFilter === "all") return tickets;
    return tickets.filter((ticket) => ticket.status === statusFilter);
  }, [statusFilter, tickets]);

  const updateStatus = useCallback(async (ticket: FacilityTicket, status: TicketStatus) => {
    setUpdatingTicketId(ticket.ticket_id);
    try {
      const updatedTicket = await updateFacilityTicketStatus(
        ticket.ticket_id,
        status,
        FACILITY_API_BASE_URL
      );
      setTickets((current) =>
        current.map((item) => item.ticket_id === updatedTicket.ticket_id ? updatedTicket : item)
      );
      const nextSummary = await fetchFacilitySummary(FACILITY_API_BASE_URL);
      setSummary(nextSummary);
      toast.success(`${updatedTicket.ticket_id} marked ${formatTicketStatus(updatedTicket.status).toLowerCase()}`);
    } catch (err) {
      const message = err instanceof Error ? err.message : "Failed to update ticket";
      toast.error(message);
    } finally {
      setUpdatingTicketId("");
    }
  }, []);

  const saveTicket = useCallback(async (ticketId: string, update: FacilityTicketUpdate) => {
    setUpdatingTicketId(ticketId);
    try {
      const updatedTicket = await updateFacilityTicket(ticketId, update, FACILITY_API_BASE_URL);
      setTickets((current) =>
        current.map((item) => item.ticket_id === updatedTicket.ticket_id ? updatedTicket : item)
      );
      const nextSummary = await fetchFacilitySummary(FACILITY_API_BASE_URL);
      setSummary(nextSummary);
      setEditingTicket(null);
      toast.success(`${updatedTicket.ticket_id} updated`);
    } catch (err) {
      const message = err instanceof Error ? err.message : "Failed to update ticket";
      toast.error(message);
    } finally {
      setUpdatingTicketId("");
    }
  }, []);

  const deleteTicket = useCallback(async (ticket: FacilityTicket) => {
    if (!window.confirm(`Delete ${ticket.ticket_id}? This removes it from the local ticket list.`)) return;
    setDeletingTicketId(ticket.ticket_id);
    try {
      await deleteFacilityTicket(ticket.ticket_id, FACILITY_API_BASE_URL);
      setTickets((current) => current.filter((item) => item.ticket_id !== ticket.ticket_id));
      const nextSummary = await fetchFacilitySummary(FACILITY_API_BASE_URL);
      setSummary(nextSummary);
      toast.success(`${ticket.ticket_id} deleted`);
    } catch (err) {
      const message = err instanceof Error ? err.message : "Failed to delete ticket";
      toast.error(message);
    } finally {
      setDeletingTicketId("");
    }
  }, []);

  return (
    <main className="facility-dashboard">
      <section className="facility-dashboard__toolbar">
        <div>
          <p className="facility-dashboard__eyebrow">School facility support</p>
          <h2>Ticket review</h2>
        </div>
        <div className="facility-dashboard__actions">
          <button
            className="facility-button facility-button--secondary"
            onClick={() => void loadTickets()}
            disabled={refreshing}
          >
            {refreshing ? <Loader2 size={16} className="facility-spin" /> : <RefreshCw size={16} />}
            Refresh
          </button>
          <button className="facility-button facility-button--primary" onClick={onStartVoice}>
            <Mic size={16} />
            Voice intake
          </button>
        </div>
      </section>

      <section className="facility-metrics" aria-label="Facility ticket summary">
        <Metric label="Open" value={summary?.open_tickets ?? 0} />
        <Metric label="Total" value={summary?.total_tickets ?? 0} />
        <Metric label="Urgent" value={summary?.urgency_counts?.urgent ?? 0} />
        <Metric label="Audit events" value={summary?.audit_events ?? 0} />
      </section>

      <TechnologyTips compact />

      <section className="facility-panel">
        <div className="facility-panel__header">
          <div className="facility-status-tabs" aria-label="Filter tickets by status">
            {statusFilters.map((filter) => (
              <button
                key={filter.value}
                className={filter.value === statusFilter ? "active" : ""}
                onClick={() => setStatusFilter(filter.value)}
              >
                {filter.label}
              </button>
            ))}
          </div>
          {summary?.sovereignty && (
            <div className="facility-sovereignty">
              {summary.sovereignty.storage_backend} · {summary.sovereignty.data_residency_region}
            </div>
          )}
        </div>

        {error && (
          <div className="facility-alert" role="alert">
            <AlertCircle size={18} />
            <span>{error}</span>
          </div>
        )}

        {loading ? (
          <div className="facility-empty">
            <Loader2 size={20} className="facility-spin" />
            Loading tickets
          </div>
        ) : filteredTickets.length === 0 ? (
          <div className="facility-empty">
            <CheckCircle2 size={20} />
            <span>No tickets match this filter.</span>
            <button className="facility-link-button" onClick={onStartVoice}>Start voice intake</button>
          </div>
        ) : (
          <div className="facility-table-wrap">
            <table className="facility-table">
              <thead>
                <tr>
                  <th>Ticket</th>
                  <th>Status</th>
                  <th>Category</th>
                  <th>Location</th>
                  <th>Urgency</th>
                  <th>Reporter</th>
                  <th>Summary</th>
                  <th>Intake notes</th>
                  <th>Updated</th>
                  <th>Actions</th>
                </tr>
              </thead>
              <tbody>
                {filteredTickets.map((ticket) => (
                  <TicketRow
                    key={ticket.ticket_id}
                    ticket={ticket}
                    updating={updatingTicketId === ticket.ticket_id || deletingTicketId === ticket.ticket_id}
                    onUpdateStatus={updateStatus}
                    onEdit={setEditingTicket}
                    onDelete={deleteTicket}
                  />
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
      {editingTicket && (
        <TicketEditDialog
          ticket={editingTicket}
          saving={updatingTicketId === editingTicket.ticket_id}
          onCancel={() => setEditingTicket(null)}
          onSave={saveTicket}
        />
      )}
    </main>
  );
}

function Metric({ label, value }: { label: string; value: number }) {
  return (
    <div className="facility-metric">
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  );
}

function TicketRow({
  ticket,
  updating,
  onUpdateStatus,
  onEdit,
  onDelete,
}: {
  ticket: FacilityTicket;
  updating: boolean;
  onUpdateStatus: (ticket: FacilityTicket, status: TicketStatus) => Promise<void>;
  onEdit: (ticket: FacilityTicket) => void;
  onDelete: (ticket: FacilityTicket) => Promise<void>;
}) {
  return (
    <tr>
      <td className="facility-table__id">
        <span>{ticket.ticket_id}</span>
        {ticket.redaction_applied && <span className="facility-redaction-badge">Redacted</span>}
      </td>
      <td>
        <span className={`facility-status facility-status--${ticket.status}`}>
          {formatTicketStatus(ticket.status)}
        </span>
      </td>
      <td>{ticket.category}</td>
      <td>{ticket.location}</td>
      <td>
        <span className={`facility-urgency facility-urgency--${ticket.urgency}`}>
          {formatTicketUrgency(ticket.urgency)}
        </span>
      </td>
      <td>{ticket.reporter}</td>
      <td className="facility-table__summary">{ticket.summary}</td>
      <td className="facility-table__summary">{ticket.transcript_snippet || "No notes"}</td>
      <td>{formatDate(ticket.updated_at)}</td>
      <td>
        <div className="facility-row-actions">
          {ticket.status !== "open" && (
            <button
              className="facility-action"
              onClick={() => void onUpdateStatus(ticket, "open")}
              disabled={updating}
            >
              Open
            </button>
          )}
          {ticket.status !== "resolved" && (
            <button
              className="facility-action facility-action--close"
              onClick={() => void onUpdateStatus(ticket, "resolved")}
              disabled={updating}
            >
              Close
            </button>
          )}
          <button
            className="facility-action"
            onClick={() => onEdit(ticket)}
            disabled={updating}
          >
            <Pencil size={14} />
            Edit
          </button>
          <button
            className="facility-action facility-action--delete"
            onClick={() => void onDelete(ticket)}
            disabled={updating}
          >
            <Trash2 size={14} />
            Delete
          </button>
        </div>
      </td>
    </tr>
  );
}

function TicketEditDialog({
  ticket,
  saving,
  onCancel,
  onSave,
}: {
  ticket: FacilityTicket;
  saving: boolean;
  onCancel: () => void;
  onSave: (ticketId: string, update: FacilityTicketUpdate) => Promise<void>;
}) {
  const [form, setForm] = useState<Required<FacilityTicketUpdate>>({
    status: ticket.status,
    category: ticket.category,
    location: ticket.location,
    summary: ticket.summary,
    urgency: ticket.urgency,
    reporter: ticket.reporter,
    transcript_snippet: ticket.transcript_snippet,
  });

  const updateField = (field: keyof Required<FacilityTicketUpdate>, value: string) => {
    setForm((current) => ({ ...current, [field]: value }));
  };

  return (
    <div className="facility-modal-backdrop" role="presentation">
      <section className="facility-modal" role="dialog" aria-modal="true" aria-labelledby="facility-edit-title">
        <header className="facility-modal__header">
          <div>
            <p className="facility-dashboard__eyebrow">{ticket.ticket_id}</p>
            <h3 id="facility-edit-title">Edit ticket</h3>
          </div>
          <button className="facility-icon-button" onClick={onCancel} aria-label="Close edit dialog">
            <X size={18} />
          </button>
        </header>
        <div className="facility-form-grid">
          <label>
            Status
            <select value={form.status} onChange={(event) => updateField("status", event.target.value)}>
              {statuses.map((status) => <option key={status} value={status}>{formatTicketStatus(status)}</option>)}
            </select>
          </label>
          <label>
            Category
            <select value={form.category} onChange={(event) => updateField("category", event.target.value)}>
              {categories.map((category) => <option key={category} value={category}>{category}</option>)}
            </select>
          </label>
          <label>
            Urgency
            <select value={form.urgency} onChange={(event) => updateField("urgency", event.target.value)}>
              {urgencies.map((urgency) => <option key={urgency} value={urgency}>{formatTicketUrgency(urgency)}</option>)}
            </select>
          </label>
          <label>
            Location
            <input value={form.location} onChange={(event) => updateField("location", event.target.value)} />
          </label>
          <label>
            Reporter
            <input value={form.reporter} onChange={(event) => updateField("reporter", event.target.value)} />
          </label>
          <label className="facility-form-grid__wide">
            Summary
            <textarea value={form.summary} onChange={(event) => updateField("summary", event.target.value)} rows={3} />
          </label>
          <label className="facility-form-grid__wide">
            Intake notes
            <textarea
              value={form.transcript_snippet}
              onChange={(event) => updateField("transcript_snippet", event.target.value)}
              rows={3}
            />
          </label>
        </div>
        <footer className="facility-modal__footer">
          <button className="facility-button facility-button--secondary" onClick={onCancel} disabled={saving}>
            Cancel
          </button>
          <button
            className="facility-button facility-button--primary"
            onClick={() => void onSave(ticket.ticket_id, form)}
            disabled={saving}
          >
            {saving ? <Loader2 size={16} className="facility-spin" /> : <Save size={16} />}
            Save
          </button>
        </footer>
      </section>
    </div>
  );
}

function formatDate(value: string): string {
  const timestamp = Date.parse(value);
  if (Number.isNaN(timestamp)) return value;
  return new Intl.DateTimeFormat(undefined, {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  }).format(timestamp);
}
