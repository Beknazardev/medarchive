"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { ArrowLeft, ArrowUpRight, GitCompareArrows, MapPin, Stethoscope } from "lucide-react";

import { FreshnessBadge } from "@/components/freshness-badge";
import { MapLinks } from "@/components/MapLinks";
import { useI18n } from "@/components/i18n-provider";
import { EmptyState } from "@/components/states/empty-state";
import { ErrorState } from "@/components/states/error-state";
import { LoadingState } from "@/components/states/loading-state";
import { Badge } from "@/components/ui/badge";
import { ButtonLink } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { getService } from "@/lib/api";
import { formatDate, formatDateTime, formatPrice } from "@/lib/format";
import type { ServiceDetailsResponse } from "@/lib/types";

type State = { key: string; data: ServiceDetailsResponse | null; error: boolean };

export function ServiceDetailsView() {
  const params = useParams<{ id: string }>();
  const { locale, t } = useI18n();
  const [state, setState] = useState<State>({ key: "", data: null, error: false });

  useEffect(() => {
    let active = true;
    getService(params.id)
      .then((data) => active && setState({ key: params.id, data, error: false }))
      .catch(() => active && setState({ key: params.id, data: null, error: true }));
    return () => { active = false; };
  }, [params.id]);

  if (state.key !== params.id) return <LoadingState label={t("serviceLoading")} />;
  if (state.error) return <ErrorState title={t("serviceUnavailable")} message={t("backendError")} />;
  if (!state.data) return <EmptyState title={t("serviceNotFound")} message={t("notAvailable")} />;
  const service = state.data.data;
  const currency = service.prices[0]?.currency ?? "KZT";

  return (
    <div className="space-y-8">
      <Link href="/search" className="inline-flex items-center gap-2 text-sm font-semibold text-[var(--muted-foreground)] hover:text-[var(--primary)]"><ArrowLeft className="h-4 w-4" />{t("backToSearch")}</Link>
      <header className="grid gap-6 border-b border-[var(--border)] pb-8 lg:grid-cols-[1fr_auto] lg:items-end">
        <div>
          <div className="mb-3 flex h-11 w-11 items-center justify-center rounded-md bg-[var(--primary-soft)] text-[var(--primary)]"><Stethoscope className="h-5 w-5" /></div>
          <h1 className="max-w-4xl text-3xl font-bold sm:text-4xl">{service.name}</h1>
          <p className="mt-3 text-sm text-[var(--muted-foreground)]"><span className="font-semibold">{t("catalogName")}:</span> {service.normalized_service.name}</p>
          <Badge className="mt-3">{service.category.name}</Badge>
        </div>
        <ButtonLink href={`/compare?service_id=${service.id}`}><GitCompareArrows className="mr-2 h-4 w-4" />{t("comparePrices")}</ButtonLink>
      </header>

      <section className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        {[
          [t("minimum"), formatPrice(service.stats.min_price, currency, locale)],
          [t("average"), formatPrice(service.stats.average_price, currency, locale)],
          [t("maximum"), formatPrice(service.stats.max_price, currency, locale)],
          [t("offers"), String(service.stats.count)],
        ].map(([label, value]) => <Card key={label} className="shadow-none"><div className="text-xs font-semibold text-[var(--muted-foreground)]">{label}</div><div className="mt-2 text-xl font-bold">{value}</div></Card>)}
      </section>

      <section>
        <h2 className="text-xl font-bold">{t("clinicsWithPrices")}</h2>
        {service.prices.length === 0 ? (
          <div className="mt-4"><EmptyState title={t("noResults")} message={t("noPrices")} /></div>
        ) : (
          <div className="mt-4 grid gap-3">
            {service.prices.map((price) => (
              <Card key={`${price.clinic_id}-${price.branch_id}-${price.currency}`} className="grid gap-4 shadow-none lg:grid-cols-[minmax(0,1fr)_auto] lg:items-center">
                <div>
                  <div className="flex flex-wrap items-center gap-2">
                    <Link href={`/clinics/${price.clinic_id}`} className="font-bold hover:text-[var(--primary)]">{price.clinic_name}</Link>
                    <FreshnessBadge state={price.freshness_state} ageDays={price.freshness_age_days} />
                  </div>
                  <div className="mt-2">
                    <MapLinks
                      providerName={price.clinic_name}
                      city={price.city}
                      address={price.address}
                      latitude={price.latitude}
                      longitude={price.longitude}
                      compact
                    />
                  </div>
                  <div className="mt-3 flex flex-wrap gap-x-4 gap-y-1 text-xs text-[var(--muted-foreground)]">
                    <span>{t("parsed")}: {formatDateTime(price.parsed_at, locale)}</span>
                    <span>{t("updated")}: {formatDate(price.updated_at, locale)}</span>
                    {price.source_url ? <Link href={price.source_url} target="_blank" rel="noreferrer" className="inline-flex items-center gap-1 font-semibold text-[var(--primary)]">{t("publicSource")}<ArrowUpRight className="h-3 w-3" /></Link> : null}
                  </div>
                </div>
                <div className="text-xl font-bold">{formatPrice(price.amount, price.currency, locale)}</div>
              </Card>
            ))}
          </div>
        )}
      </section>
    </div>
  );
}
