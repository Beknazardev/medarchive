"use client";

import { Activity } from "lucide-react";

import { useI18n } from "@/components/i18n-provider";
import { Container } from "@/components/layout/container";

export function SiteFooter() {
  const { t } = useI18n();
  return (
    <footer className="mt-16 border-t border-[var(--border)] bg-[var(--surface)]">
      <Container className="flex flex-col gap-4 py-7 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex items-center gap-2 font-semibold">
          <Activity className="h-4 w-4 text-[var(--primary)]" />
          MedServicePrice.kz
        </div>
        <div className="max-w-2xl text-sm text-[var(--muted-foreground)] sm:text-right">
          <p>{t("footerText")}</p>
          <p className="mt-1 text-xs">{t("footerNote")}</p>
        </div>
      </Container>
    </footer>
  );
}
