"use client";

import { FormEvent, useMemo, useState } from "react";
import { CheckCircle2, FileJson, KeyRound, Loader2, ShieldAlert } from "lucide-react";

import { useI18n } from "@/components/i18n-provider";
import { ErrorState } from "@/components/states/error-state";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { importPrices } from "@/lib/api";
import type { ImportPricesRequest, ImportPricesResponse } from "@/lib/types";

const examplePayload: ImportPricesRequest = {
  source: "manual_admin_import",
  source_url: "https://example.kz/prices",
  source_batch_id: "manual_demo_001",
  clinic: {
    external_id: "clinic_manual_001",
    name: "Пример клиники",
    city: "Astana",
    address: "улица Примерная, 10",
    phone: "+77001234567",
    website: "https://example.kz",
  },
  branch: {
    external_id: "branch_manual_001",
    name: "Главный филиал",
    city: "Astana",
    address: "улица Примерная, 10",
  },
  services: [
    {
      external_id: "srv_manual_001",
      name: "МРТ головного мозга",
      category: "МРТ",
      price: 25000,
      currency: "KZT",
      updated_at: "2026-06-17",
      source_url: "https://example.kz/prices/mri",
      parsed_at: "2026-06-27T09:00:00Z",
      is_available: true,
    },
  ],
};

function isImportPayload(value: unknown): value is ImportPricesRequest {
  if (!value || typeof value !== "object") return false;
  const payload = value as Partial<ImportPricesRequest>;
  return typeof payload.source === "string" && Boolean(payload.clinic) && Array.isArray(payload.services);
}

export function AdminImportForm() {
  const { t } = useI18n();
  const [apiKey, setApiKey] = useState("");
  const [jsonText, setJsonText] = useState(JSON.stringify(examplePayload, null, 2));
  const [result, setResult] = useState<ImportPricesResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const canSubmit = useMemo(() => apiKey.trim() && jsonText.trim() && !submitting, [apiKey, jsonText, submitting]);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);
    setResult(null);
    let parsed: unknown;
    try {
      parsed = JSON.parse(jsonText);
    } catch {
      setError("JSON syntax error");
      return;
    }
    if (!isImportPayload(parsed)) {
      setError("JSON must contain source, clinic and services.");
      return;
    }
    setSubmitting(true);
    try {
      setResult(await importPrices(parsed, apiKey.trim()));
    } catch {
      setError(t("backendError"));
    } finally {
      setSubmitting(false);
    }
  }

  const summary = result?.data;
  const metrics = summary ? [
    [t("received"), summary.received_count],
    [t("created"), summary.created_count],
    [t("changed"), summary.updated_count],
    [t("unchanged"), summary.unchanged_count],
    [t("errors"), summary.error_count],
  ] : [];

  return (
    <div className="space-y-7">
      <header className="max-w-3xl">
        <div className="mb-3 inline-flex items-center gap-2 rounded-md bg-[var(--warning-soft)] px-3 py-1.5 text-xs font-bold text-[var(--warning)]">
          <ShieldAlert className="h-3.5 w-3.5" />Demo / Admin
        </div>
        <h1 className="text-3xl font-bold sm:text-4xl">{t("ingestionPageTitle")}</h1>
        <p className="mt-2 text-sm leading-6 text-[var(--muted-foreground)]">{t("ingestionPageDescription")}</p>
      </header>

      <form onSubmit={handleSubmit} className="grid gap-5 lg:grid-cols-[340px_minmax(0,1fr)]">
        <div className="space-y-5">
          <Card className="space-y-5 shadow-none">
            <div className="flex items-center gap-2 font-semibold"><KeyRound className="h-5 w-5 text-[var(--primary)]" />{t("apiKey")}</div>
            <p className="text-xs leading-5 text-[var(--muted-foreground)]">{t("apiKeyHelp")}</p>
            <Input type="password" value={apiKey} onChange={(event) => setApiKey(event.target.value)} placeholder="X-API-Key" autoComplete="off" />
            <Button type="submit" disabled={!canSubmit} className="w-full">
              {submitting ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : null}
              {submitting ? t("importing") : t("importAction")}
            </Button>
            <Button type="button" variant="secondary" className="w-full" onClick={() => setJsonText(JSON.stringify(examplePayload, null, 2))}>
              <FileJson className="mr-2 h-4 w-4" />{t("loadExample")}
            </Button>
          </Card>
          {error ? <ErrorState title={t("importFailed")} message={error} /> : null}
          {summary ? (
            <div className="rounded-lg border border-emerald-300 bg-emerald-50 p-4 text-emerald-900 dark:border-emerald-900 dark:bg-emerald-950 dark:text-emerald-200">
              <div className="flex gap-3"><CheckCircle2 className="h-5 w-5 flex-none" /><div><div className="font-semibold">{t("importComplete")}</div><div className="mt-1 text-xs">{t("status")}: {summary.status}</div></div></div>
            </div>
          ) : null}
        </div>

        <Card className="shadow-none">
          <div className="font-semibold">{t("jsonData")}</div>
          <p className="mt-1 text-xs text-[var(--muted-foreground)]">{t("jsonHelp")}</p>
          <textarea
            value={jsonText}
            onChange={(event) => setJsonText(event.target.value)}
            className="mt-4 min-h-[580px] w-full resize-y rounded-md border border-[var(--border)] bg-[var(--background)] p-4 font-mono text-xs leading-5 text-[var(--foreground)] outline-none focus:border-[var(--primary)] focus:ring-2 focus:ring-[var(--primary-soft)]"
            spellCheck={false}
            aria-label={t("jsonData")}
          />
        </Card>
      </form>

      {summary ? (
        <section className="space-y-4">
          <div className="flex items-center justify-between"><h2 className="text-xl font-bold">{t("importSummary")}</h2><Badge>{summary.status}</Badge></div>
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-5">
            {metrics.map(([label, value]) => <Card key={String(label)} className="shadow-none"><div className="text-xs text-[var(--muted-foreground)]">{label}</div><div className="mt-2 text-xl font-bold">{value}</div></Card>)}
          </div>
          {summary.errors.length ? (
            <Card className="shadow-none">
              <h3 className="font-semibold">{t("importErrors")}</h3>
              <div className="mt-3 space-y-2">
                {summary.errors.map((item) => (
                  <div key={`${item.index}-${item.code}`} className="rounded-md bg-[var(--danger-soft)] p-3 text-sm">
                    <div className="font-semibold text-[var(--danger)]">{item.code} · {item.field ?? t("field")}</div>
                    <div className="mt-1 text-[var(--muted-foreground)]">{item.message}</div>
                  </div>
                ))}
              </div>
            </Card>
          ) : null}
        </section>
      ) : null}
    </div>
  );
}
