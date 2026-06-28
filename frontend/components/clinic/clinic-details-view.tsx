"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { ArrowLeft, ArrowUpRight, Building2, Globe2, MapPin, Phone } from "lucide-react";

import { FreshnessBadge } from "@/components/freshness-badge";
import { MapLinks } from "@/components/MapLinks";
import { useI18n } from "@/components/i18n-provider";
import { EmptyState } from "@/components/states/empty-state";
import { ErrorState } from "@/components/states/error-state";
import { LoadingState } from "@/components/states/loading-state";
import { Badge } from "@/components/ui/badge";
import { Card } from "@/components/ui/card";
import { getClinic } from "@/lib/api";
import { formatDate, formatDateTime, formatPrice } from "@/lib/format";
import type { ClinicDetailsResponse } from "@/lib/types";

type State = { key: string; data: ClinicDetailsResponse | null; error: boolean };

export function ClinicDetailsView() {
  const params = useParams<{ id: string }>();
  const { locale, t } = useI18n();
  const [state, setState] = useState<State>({ key: "", data: null, error: false });

  useEffect(() => {
    let active = true;
    getClinic(params.id)
      .then((data) => active && setState({ key: params.id, data, error: false }))
      .catch(() => active && setState({ key: params.id, data: null, error: true }));
    return () => { active = false; };
  }, [params.id]);

  if (state.key !== params.id) return <LoadingState label={t("clinicLoading")} />;
  if (state.error) return <ErrorState title={t("clinicUnavailable")} message={t("backendError")} />;
  if (!state.data) return <EmptyState title={t("clinicNotFound")} message={t("notAvailable")} />;
  const clinic = state.data.data;

  return (
    <div className="space-y-8">
      <Link href="/search" className="inline-flex items-center gap-2 text-sm font-semibold text-[var(--muted-foreground)] hover:text-[var(--primary)]">
        <ArrowLeft className="h-4 w-4" />{t("backToSearch")}
      </Link>

      <header className="grid gap-6 border-b border-[var(--border)] pb-8 lg:grid-cols-[1fr_auto]">
        <div>
          <div className="mb-3 flex h-11 w-11 items-center justify-center rounded-md bg-[var(--primary-soft)] text-[var(--primary)]"><Building2 className="h-5 w-5" /></div>
          <h1 className="text-3xl font-bold sm:text-4xl">{clinic.name}</h1>
          <div className="mt-4 flex flex-wrap gap-x-5 gap-y-2 text-sm text-[var(--muted-foreground)]">
            <span className="inline-flex items-center gap-2"><MapPin className="h-4 w-4" />{clinic.city}</span>
            {clinic.phone ? <span className="inline-flex items-center gap-2"><Phone className="h-4 w-4" />{clinic.phone}</span> : null}
            {clinic.website ? <Link href={clinic.website} target="_blank" rel="noreferrer" className="inline-flex items-center gap-2 font-semibold text-[var(--primary)]"><Globe2 className="h-4 w-4" />{t("clinicWebsite")}<ArrowUpRight className="h-3 w-3" /></Link> : null}
          </div>
        </div>
        <div className="grid grid-cols-2 gap-3">
          <Metric value={clinic.branches.length} label={t("branches")} />
          <Metric value={clinic.services.length} label={t("offers")} />
        </div>
      </header>

      <section>
        <h2 className="text-xl font-bold">{t("branches")}</h2>
        <div className="mt-4 grid gap-3 md:grid-cols-2 xl:grid-cols-3">
          {clinic.branches.map((branch) => (
            <Card key={branch.id} className="shadow-none">
              <div className="font-semibold">{branch.name ?? t("branch")}</div>
              <div className="mt-2">
                <MapLinks
                  providerName={clinic.name}
                  city={branch.city}
                  address={branch.address}
                  latitude={branch.latitude}
                  longitude={branch.longitude}
                />
              </div>
              {branch.phone ? <div className="mt-2 flex gap-2 text-sm text-[var(--muted-foreground)]"><Phone className="h-4 w-4" />{branch.phone}</div> : null}
            </Card>
          ))}
        </div>
      </section>

      <section>
        <h2 className="text-xl font-bold">{t("servicesAndPrices")}</h2>
        {clinic.services.length === 0 ? (
          <div className="mt-4"><EmptyState title={t("noResults")} message={t("noServicePrices")} /></div>
        ) : (
          <div className="mt-4 grid gap-3">
            {clinic.services.map((service) => (
              <Card key={`${service.service_id}-${service.currency}`} className="grid gap-4 shadow-none md:grid-cols-[minmax(0,1fr)_auto] md:items-center">
                <div>
                  <div className="flex flex-wrap gap-2"><Badge>{service.category}</Badge><FreshnessBadge state={service.freshness_state} ageDays={service.freshness_age_days} /></div>
                  <Link href={`/services/${service.service_id}`} className="mt-3 block font-bold hover:text-[var(--primary)]">{service.name}</Link>
                  <div className="mt-3 flex flex-wrap gap-x-4 gap-y-1 text-xs text-[var(--muted-foreground)]">
                    <span>{t("parsed")}: {formatDateTime(service.parsed_at, locale)}</span>
                    <span>{t("updated")}: {formatDate(service.updated_at, locale)}</span>
                    {service.source_url ? <Link href={service.source_url} target="_blank" rel="noreferrer" className="font-semibold text-[var(--primary)]">{t("publicSource")}</Link> : null}
                  </div>
                </div>
                <div className="text-xl font-bold">{formatPrice(service.price, service.currency, locale)}</div>
              </Card>
            ))}
          </div>
        )}
      </section>
    </div>
  );
}

function Metric({ value, label }: { value: number; label: string }) {
  return <div className="min-w-28 rounded-lg border border-[var(--border)] bg-[var(--surface)] p-4 text-center shadow-[var(--shadow)]"><div className="text-2xl font-bold">{value}</div><div className="mt-1 text-xs text-[var(--muted-foreground)]">{label}</div></div>;
}
