import type { TranslationStatus } from "../types/api";

const enumMap: Record<number, string> = {
  0: "Queued",
  1: "Processing",
  2: "Completed",
  3: "Failed",
  4: "Cancelled"
};

export function normalizeStatus(status?: TranslationStatus | null) {
  if (typeof status === "number") return enumMap[status] ?? "Unknown";
  if (!status) return "Unknown";
  const raw = String(status);
  return raw.charAt(0).toUpperCase() + raw.slice(1).toLowerCase();
}

export function isStatus(status: TranslationStatus | undefined | null, expected: string) {
  return normalizeStatus(status).toLowerCase() === expected.toLowerCase();
}

export function isActiveStatus(status: TranslationStatus | undefined | null) {
  const normalized = normalizeStatus(status).toLowerCase();
  return normalized === "queued" || normalized === "processing";
}
