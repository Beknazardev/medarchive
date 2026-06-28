"use client";

import Link from "next/link";
import { ArrowUpRight, Building2, GitCompareArrows, MapPin } from "lucide-react";

import { FreshnessBadge } from "@/components/freshness-badge";
import { MapLinks } from "@/components/MapLinks";
import { useI18n } from "@/components/i18n-provider";
import { Badge } from "@/components/ui/badge";
import { ButtonLink } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { formatDate, formatDateTime, formatPrice } from "@/lib/format";
import type { SearchServiceItem } from "@/lib/types";

export function PriceCard({ item }: { item: SearchServiceItem }) {
  const { locale, t } = useI18n();
  const normalizedDiffers = item.normalized_service_name.trim().toLocaleLowerCase() !== item.service_name.trim().toLocaleLowerCase();
  const displayName = item.display_service_name || item.service_name;
  const displayCategory = item.display_category_name || item.category;

  return (
    <Card className="p-0">
      <div className="grid lg:grid-cols-[minmax(0,1fr)_220px]">
        <div className="p-5 sm:p-6">
          <div className="flex flex-wrap items-center gap-2">
            <Badge>{displayCategory}</Badge>
            <FreshnessBadge state={item.price.freshness_state} ageDays={item.price.freshness_age_days} />
          </div>
          <Link href={`/services/${item.service_id}`} className="mt-4 block text-lg font-bold leading-6 hover:text-[var(--primary)] sm:text-xl">
            {displayName}
          </Link>
          {normalizedDiffers ? (
            <p className="mt-2 text-sm text-[var(--muted-foreground)]">
              <span className="font-semibold">{t("normalizedName")}:</span> {item.normalized_service_name}
            </p>
          ) : null}

          <div className="mt-5 grid gap-3 text-sm sm:grid-cols-2">
            <Link href={`/clinics/${item.clinic.id}`} className="flex items-start gap-2 font-semibold hover:text-[var(--primary)]">
              <Building2 className="mt-0.5 h-4 w-4 flex-none text-[var(--muted-foreground)]" />
              {item.clinic.name}
            </Link>
            <MapLinks
              providerName={item.clinic.name}
              city={item.branch.city}
              address={item.branch.address}
              latitude={item.branch.latitude}
              longitude={item.branch.longitude}
              compact
            />
          </div>

          <div className="mt-5 flex flex-wrap gap-2">
            <ButtonLink href={`/compare?normalized_service_id=${item.normalized_service_id}`} variant="secondary">
              <GitCompareArrows className="mr-2 h-4 w-4" />
              {t("compare")}
            </ButtonLink>
            <ButtonLink href={`/clinics/${item.clinic.id}`} variant="ghost">{t("openClinic")}</ButtonLink>
            <ButtonLink href={`/services/${item.service_id}`} variant="ghost">{t("openService")}</ButtonLink>
          </div>
        </div>

        <aside className="border-t border-[var(--border)] bg-[var(--surface-muted)] p-5 lg:border-l lg:border-t-0">
          <div className="text-2xl font-bold">{formatPrice(item.price.amount, item.price.currency, locale)}</div>
          <dl className="mt-5 space-y-3 text-xs">
            <div>
              <dt className="font-semibold text-[var(--muted-foreground)]">{t("parsed")}</dt>
              <dd className="mt-1">{formatDateTime(item.price.parsed_at, locale)}</dd>
            </div>
            <div>
              <dt className="font-semibold text-[var(--muted-foreground)]">{t("updated")}</dt>
              <dd className="mt-1">{formatDate(item.price.updated_at, locale)}</dd>
            </div>
          </dl>
          <div className="mt-5">
            {item.price.source_url ? (
              <Link
                href={item.price.source_url}
                target="_blank"
                rel="noreferrer"
                className="inline-flex items-center gap-1.5 text-xs font-bold text-[var(--primary)] hover:underline"
              >
                {t("publicSource")}
                <ArrowUpRight className="h-3.5 w-3.5" />
              </Link>
            ) : (
              <span className="text-xs text-[var(--muted-foreground)]">{t("noSource")}</span>
            )}
          </div>
        </aside>
      </div>
    </Card>
  );
}
