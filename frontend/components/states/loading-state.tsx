"use client";

import { useI18n } from "@/components/i18n-provider";
import { Skeleton } from "@/components/ui/skeleton";

export function LoadingState({ label }: { label?: string }) {
  const { t } = useI18n();
  return (
    <div className="space-y-3" aria-busy="true" aria-label={label ?? t("loading")}>
      <Skeleton className="h-28 w-full" />
      <Skeleton className="h-28 w-full" />
      <Skeleton className="h-28 w-full" />
    </div>
  );
}
