import { localeTags, type Locale } from "@/lib/i18n";

export function formatPrice(
  value: string | number | null | undefined,
  currency = "KZT",
  locale: Locale = "ru",
  fallback = "—",
) {
  if (value === null || value === undefined) return fallback;
  const amount = typeof value === "number" ? value : Number(value);
  if (Number.isNaN(amount)) return `${value} ${currency}`;
  return new Intl.NumberFormat(localeTags[locale], {
    style: "currency",
    currency,
    maximumFractionDigits: 0,
  }).format(amount);
}

export function formatDate(value: string | null | undefined, locale: Locale = "ru", fallback = "—") {
  if (!value) return fallback;
  const date = new Date(value);
  if (Number.isNaN(date.valueOf())) return fallback;
  return new Intl.DateTimeFormat(localeTags[locale], {
    year: "numeric",
    month: "short",
    day: "numeric",
  }).format(date);
}

export function formatDateTime(value: string | null | undefined, locale: Locale = "ru", fallback = "—") {
  if (!value) return fallback;
  const date = new Date(value);
  if (Number.isNaN(date.valueOf())) return fallback;
  return new Intl.DateTimeFormat(localeTags[locale], {
    year: "numeric",
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  }).format(date);
}
