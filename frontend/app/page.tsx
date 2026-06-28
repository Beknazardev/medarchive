"use client";

import Link from "next/link";
import {
  ArrowRight,
  Database,
  FileCheck2,
  GitCompareArrows,
  RefreshCw,
  Search,
  ShieldCheck,
  TimerReset,
} from "lucide-react";

import { useI18n } from "@/components/i18n-provider";
import { Container } from "@/components/layout/container";
import { SearchBox } from "@/components/search/search-box";
import { ButtonLink } from "@/components/ui/button";

export default function HomePage() {
  const { locale, t } = useI18n();
  const features = [
    { icon: Search, title: t("oneSearch"), text: t("oneSearchText") },
    { icon: ShieldCheck, title: t("sourceFirst"), text: t("sourceFirstText") },
    { icon: TimerReset, title: t("freshnessTitle"), text: t("freshnessText") },
    { icon: RefreshCw, title: t("ingestionTitle"), text: t("ingestionText") },
  ];
  const pipeline = [
    t("pipelineSource"),
    t("pipelineAdapter"),
    t("pipelineImport"),
    t("pipelineValidation"),
    t("pipelineCatalog"),
    t("pipelineUi"),
  ];
  const examples = locale === "en"
    ? ["PCR", "ultrasound", "MRI", "therapist"]
    : locale === "kk"
      ? ["ПТР", "УДЗ", "МРТ", "терапевт қабылдауы"]
      : ["ПЦР", "УЗИ", "МРТ", "терапевт"];

  return (
    <>
      <section className="border-b border-[var(--border)] bg-[var(--surface)]">
        <Container className="grid min-h-[560px] gap-12 py-14 lg:grid-cols-[minmax(0,1.25fr)_minmax(320px,0.75fr)] lg:items-center lg:py-20">
          <div>
            <div className="mb-5 inline-flex items-center gap-2 rounded-md bg-[var(--primary-soft)] px-3 py-1.5 text-xs font-bold uppercase text-[var(--primary)]">
              <Database className="h-3.5 w-3.5" />
              {t("heroEyebrow")}
            </div>
            <h1 className="max-w-4xl text-4xl font-bold leading-tight text-[var(--foreground)] sm:text-5xl lg:text-6xl">
              {t("heroTitle")}
            </h1>
            <p className="mt-5 max-w-3xl text-base leading-7 text-[var(--muted-foreground)] sm:text-lg">
              {t("heroSubtitle")}
            </p>
            <div className="mt-8 max-w-3xl">
              <SearchBox prominent />
              <div className="mt-3 flex flex-wrap items-center gap-2 text-xs text-[var(--muted-foreground)]">
                <span>{t("popularQueries")}:</span>
                {examples.map((query) => (
                  <Link key={query} href={`/search?q=${encodeURIComponent(query)}`} className="font-semibold hover:text-[var(--primary)]">
                    {query}
                  </Link>
                ))}
              </div>
            </div>
            <div className="mt-7 flex flex-wrap gap-3">
              <ButtonLink href="/compare" variant="secondary">
                <GitCompareArrows className="mr-2 h-4 w-4" />
                {t("comparePrices")}
              </ButtonLink>
              <ButtonLink href="/admin/import" variant="ghost">
                <FileCheck2 className="mr-2 h-4 w-4" />
                {t("navImport")}
              </ButtonLink>
            </div>
          </div>

          <aside className="border-l-0 border-[var(--border)] lg:border-l lg:pl-10">
            <p className="text-xs font-bold uppercase text-[var(--muted-foreground)]">{t("demoStats")}</p>
            <div className="mt-5 grid grid-cols-3 gap-3 lg:grid-cols-1">
              {[
                ["3", t("publicSources")],
                ["105", t("priceRecords")],
                ["1 281", t("catalogServices")],
              ].map(([value, label]) => (
                <div key={label} className="border-b border-[var(--border)] pb-4">
                  <div className="text-2xl font-bold text-[var(--foreground)] sm:text-3xl">{value}</div>
                  <div className="mt-1 text-xs leading-5 text-[var(--muted-foreground)] sm:text-sm">{label}</div>
                </div>
              ))}
            </div>
          </aside>
        </Container>
      </section>

      <section>
        <Container className="py-14">
          <div className="grid gap-px overflow-hidden rounded-lg border border-[var(--border)] bg-[var(--border)] md:grid-cols-2 xl:grid-cols-4">
            {features.map(({ icon: Icon, title, text }) => (
              <article key={title} className="bg-[var(--surface)] p-6">
                <span className="flex h-10 w-10 items-center justify-center rounded-md bg-[var(--primary-soft)] text-[var(--primary)]">
                  <Icon className="h-5 w-5" />
                </span>
                <h2 className="mt-5 text-base font-semibold">{title}</h2>
                <p className="mt-2 text-sm leading-6 text-[var(--muted-foreground)]">{text}</p>
              </article>
            ))}
          </div>
        </Container>
      </section>

      <section className="border-y border-[var(--border)] bg-[var(--surface)]">
        <Container className="py-14">
          <div className="max-w-2xl">
            <h2 className="text-2xl font-bold">{t("pipelineTitle")}</h2>
            <p className="mt-2 text-sm leading-6 text-[var(--muted-foreground)]">{t("pipelineText")}</p>
          </div>
          <div className="mt-7 grid gap-2 sm:grid-cols-3 xl:grid-cols-6">
            {pipeline.map((step, index) => (
              <div key={step} className="flex items-center gap-2 rounded-md border border-[var(--border)] bg-[var(--background)] px-3 py-3">
                <span className="flex h-6 w-6 flex-none items-center justify-center rounded bg-[var(--primary-soft)] text-xs font-bold text-[var(--primary)]">
                  {index + 1}
                </span>
                <span className="text-xs font-semibold">{step}</span>
                {index < pipeline.length - 1 ? <ArrowRight className="ml-auto hidden h-3.5 w-3.5 text-[var(--muted-foreground)] xl:block" /> : null}
              </div>
            ))}
          </div>
        </Container>
      </section>
    </>
  );
}
