export const FACILITY_TICKET_CREATED_STOP_DELAY_MS = 11000;
export const FACILITY_TICKET_CREATED_FALLBACK_STOP_DELAY_MS = 25000;

export function shouldReturnToDashboardAfterTicketCreated(elapsedMs: number): boolean {
  return elapsedMs >= FACILITY_TICKET_CREATED_STOP_DELAY_MS;
}

export function isFacilityTicketClosingTranscript(text: string, ticketId: string): boolean {
  const normalizedText = text.toLowerCase();
  const normalizedTicketId = ticketId.toLowerCase();
  return (
    normalizedText.includes(normalizedTicketId) &&
    (normalizedText.includes("thank you") ||
      normalizedText.includes("goodbye") ||
      normalizedText.includes("dashboard"))
  );
}
