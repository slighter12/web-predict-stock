import type { ImportantEventPayload, LifecycleRecordPayload } from "../types";

const toLocalInputValue = (sliceLength: 10 | 16) =>
  new Date(Date.now() - new Date().getTimezoneOffset() * 60_000)
    .toISOString()
    .slice(0, sliceLength);

export const createDefaultLifecycleRecordForm = (): LifecycleRecordPayload => ({
  symbol: "2330",
  market: "TW",
  event_type: "listing",
  effective_date: toLocalInputValue(10),
  reference_symbol: "",
  source_name: "manual_data_plane",
  raw_payload_id: undefined,
  archive_object_reference: "",
  notes: "",
});

export const createDefaultImportantEventForm = (): ImportantEventPayload => ({
  symbol: "2330",
  market: "TW",
  event_type: "cash_dividend",
  effective_date: toLocalInputValue(10),
  event_publication_ts: toLocalInputValue(16),
  timestamp_source_class: "official_exchange",
  source_name: "manual_data_plane",
  raw_payload_id: undefined,
  archive_object_reference: "",
  notes: "",
});

export const toOptionalNumber = (value: string) => {
  const trimmed = value.trim();
  if (!trimmed) {
    return undefined;
  }
  const parsed = Number(trimmed);
  return Number.isFinite(parsed) ? parsed : undefined;
};

export const toDateTimeValue = (value: string) => {
  if (!value.trim()) {
    return new Date().toISOString();
  }
  return new Date(value).toISOString();
};
