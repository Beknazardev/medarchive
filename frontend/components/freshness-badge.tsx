"use client";

import { CircleAlert, CircleCheck, Clock3, HelpCircle } from "lucide-react";

import { useI18n } from "@/components/i18n-provider";
import type { FreshnessState } from "@/lib/types";
import { cn } from "@/lib/utils";

const styles: Record<FreshnessState, string> = {
  fresh: "bg-emerald-100 text-emerald-800 dark:bg-emerald-950 dark:text-emerald-300",
  aging: "bg-amber-100 text-amber-800 dark:bg-amber-950 dark:text-amber-300",
  stale: "bg-red-100 text-red-800 dark:bg-red-950 dark:text-red-300",
  unknown: "bg-[var(--surface-muted)] text-[var(--muted-foreground)]",
};

const icons = {
  fresh: CircleCheck,
  aging: Clock3,
  stale: CircleAlert,
  unknown: HelpCircle,
};

export function FreshnessBadge({
  state,
  ageDays,
  className,
}: {
  state: FreshnessState;
  ageDays?: number | null;
  className?: string;
}) {
  const { t } = useI18n();
  const label = {
    fresh: t("freshnessFresh"),
    aging: t("freshnessAging"),
    stale: t("freshnessStale"),
    unknown: t("freshnessUnknown"),
  }[state];
  const Icon = icons[state];

  return (
    <span className={cn("inline-flex items-center gap-1.5 rounded-md px-2 py-1 text-xs font-semibold", styles[state], className)}>
      <Icon className="h-3.5 w-3.5" aria-hidden="true" />
      {label}
      {ageDays !== null && ageDays !== undefined ? ` · ${ageDays} ${t("days")}` : ""}
    </span>
  );
}
