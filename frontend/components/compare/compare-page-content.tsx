"use client";

import { FormEvent, useEffect, useState } from "react";
import Link from "next/link";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { ArrowUpRight, GitCompareArrows, MapPin, Trophy } from "lucide-react";

import { FreshnessBadge } from "@/components/freshness-badge";
import { MapLinks } from "@/components/MapLinks";
import { useI18n } from "@/components/i18n-provider";
import { EmptyState } from "@/components/states/empty-state";
import { ErrorState } from "@/components/states/error-state";
import { LoadingState } from "@/components/states/loading-state";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { comparePrices } from "@/lib/api";
import { formatDate, formatDateTime, formatPrice } from "@/lib/format";
import type { ComparePricesResponse } from "@/lib/types";
import { cn } from "@/lib/utils";

type CompareSort = "price_asc" | "price_desc" | "updated_desc";
type CompareState = { key: string; data: ComparePricesResponse | null; error: boolean };

export function ComparePageContent() {
  const { locale, t } = useI18n();
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const q = searchParams.get("q") ?? "";
  const serviceId = searchParams.get("service_id") ?? "";
  const normalizedServiceId = searchParams.get("normalized_service_id") ?? "";
  const city = searchParams.get("city") ?? "";
  const category = searchParams.get("category") ?? "";
  const sort = toSort(searchParams.get("sort"));
  const [state, setState] = useState<CompareState>({ key: "", data: null, error: false });
  const hasTarget = Boolean(q.trim() || serviceId || normalizedServiceId);
  const requestKey = hasTarget ? [q, serviceId, normalizedServiceId, city, category, sort].join("|") : "";

  useEffect(() => {
    if (!requestKey) return;
    let active = true;
    comparePrices({
      q: q.trim() || undefined,
      service_id: serviceId ? Number(serviceId) : undefined,
      normalized_service_id: normalizedServiceId ? Number(normalizedServiceId) : undefined,
      city,
      category,
      sort,
    })
      .then((data) => active && setState({ key: requestKey, data, error: false }))
      .catch(() => active && setState({ key: requestKey, data: null, error: true }));
    return () => { active = false; };
  }, [requestKey, q, serviceId, normalizedServiceId, city, category, sort]);

  const data = state.key === requestKey ? state.data : null;
  const error = state.key === requestKey && state.error;
  const loading = Boolean(requestKey) && state.key !== requestKey;
  const currency = data?.data.stats.currency ?? "KZT";
  const minimum = data?.data.stats.min_price;
  const suggestions = locale === "en" ? ["PCR", "ultrasound", "MRI"] : locale === "kk" ? ["ПТР", "УДЗ", "МРТ"] : ["ПЦР", "УЗИ", "МРТ"];

  function applyFilters(filters: { q: string; city: string; category: string; sort: CompareSort }) {
    const params = new URLSearchParams();
    if (serviceId) params.set("service_id", serviceId);
    else if (normalizedServiceId) params.set("normalized_service_id", normalizedServiceId);
    else if (filters.q.trim()) params.set("q", filters.q.trim());
    if (filters.city.trim()) params.set("city", filters.city.trim());
    if (filters.category.trim()) params.set("category", filters.category.trim());
    params.set("sort", filters.sort);
    router.push(`${pathname}?${params.toString()}`);
  }

  return (
    <div className="space-y-6">
      <header className="max-w-3xl">
        <h1 className="text-3xl font-bold sm:text-4xl">{t("compareTitle")}</h1>
        <p className="mt-2 text-sm leading-6 text-[var(--muted-foreground)]">{t("compareDescription")}</p>
      </header>

      <Card className="shadow-none">
        <div className="mb-4 flex items-center gap-2 font-semibold">
          <GitCompareArrows className="h-5 w-5 text-[var(--primary)]" />
          {t("comparisonQuery")}
        </div>
        <CompareFilterForm
          key={[q, city, category, sort, serviceId, normalizedServiceId].join("|")}
          initialValues={{ q, city, category, sort }}
          locked={Boolean(serviceId || normalizedServiceId)}
          onApply={applyFilters}
        />
      </Card>

      {!hasTarget ? (
        <EmptyState title={t("noComparison")} message={t("noComparisonText")} queries={suggestions} target="/compare" />
      ) : loading ? (
        <LoadingState label={t("compareLoading")} />
      ) : error ? (
        <ErrorState title={t("compareError")} message={t("backendError")} />
      ) : data && data.data.items.length > 0 ? (
        <>
          <section className="grid grid-cols-2 gap-3 lg:grid-cols-4">
            {[
              [t("offers"), String(data.data.stats.count)],
              [t("minimum"), formatPrice(data.data.stats.min_price, currency, locale)],
              [t("average"), formatPrice(data.data.stats.average_price, currency, locale)],
              [t("maximum"), formatPrice(data.data.stats.max_price, currency, locale)],
            ].map(([label, value], index) => (
              <Card key={label} className={cn("shadow-none", index === 1 && "border-[var(--primary)]")}>
                <div className="text-xs font-semibold text-[var(--muted-foreground)]">{label}</div>
                <div className="mt-2 text-xl font-bold">{value}</div>
              </Card>
            ))}
          </section>

          <div className="hidden overflow-hidden rounded-lg border border-[var(--border)] bg-[var(--surface)] lg:block">
            <table className="w-full text-left text-sm">
              <thead className="bg-[var(--surface-muted)] text-xs text-[var(--muted-foreground)]">
                <tr>
                  <th className="px-4 py-3 font-semibold">{t("clinic")}</th>
                  <th className="px-4 py-3 font-semibold">{t("service")}</th>
                  <th className="px-4 py-3 font-semibold">{t("city")} / {t("address")}</th>
                  <th className="px-4 py-3 font-semibold">{t("minimum")}</th>
                  <th className="px-4 py-3 font-semibold">{t("source")}</th>
                  <th className="px-4 py-3 font-semibold">{t("dates")}</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[var(--border)]">
                {data.data.items.map((item) => {
                  const cheapest = minimum !== null && Number(item.price) === Number(minimum);
                  return (
                    <tr key={`${item.clinic_id}-${item.branch_id}-${item.service_id}`} className={cheapest ? "bg-[var(--primary-soft)]/50" : ""}>
                      <td className="px-4 py-4">
                        <Link href={`/clinics/${item.clinic_id}`} className="font-semibold hover:text-[var(--primary)]">{item.clinic_name}</Link>
                        {cheapest ? <Badge className="mt-2 flex w-fit gap-1"><Trophy className="h-3 w-3" />{t("cheapest")}</Badge> : null}
                      </td>
                      <td className="max-w-xs px-4 py-4"><Link href={`/services/${item.service_id}`} className="font-medium hover:text-[var(--primary)]">{item.display_service_name || item.service_name}</Link></td>
                      <td className="max-w-xs px-4 py-4">
                        <MapLinks
                          providerName={item.clinic_name}
                          city={item.city}
                          address={item.address}
                          latitude={item.latitude}
                          longitude={item.longitude}
                          compact
                        />
                      </td>
                      <td className="whitespace-nowrap px-4 py-4 text-base font-bold">{formatPrice(item.price, item.currency, locale)}</td>
                      <td className="px-4 py-4">
                        <FreshnessBadge state={item.freshness_state} ageDays={item.freshness_age_days} />
                        {item.source_url ? <Link href={item.source_url} target="_blank" rel="noreferrer" className="mt-2 flex items-center gap-1 text-xs font-semibold text-[var(--primary)]">{t("publicSource")}<ArrowUpRight className="h-3 w-3" /></Link> : null}
                      </td>
                      <td className="px-4 py-4 text-xs text-[var(--muted-foreground)]">
                        <div>{t("parsed")}: {formatDateTime(item.parsed_at, locale)}</div>
                        <div className="mt-1">{t("updated")}: {formatDate(item.updated_at, locale)}</div>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>

          <div className="space-y-3 lg:hidden">
            {data.data.items.map((item) => {
              const cheapest = minimum !== null && Number(item.price) === Number(minimum);
              return (
                <Card key={`${item.clinic_id}-${item.branch_id}-${item.service_id}`} className={cheapest ? "border-[var(--primary)]" : ""}>
                  <div className="flex items-start justify-between gap-3">
                    <div>
                      {cheapest ? <Badge className="mb-2 gap-1"><Trophy className="h-3 w-3" />{t("cheapest")}</Badge> : null}
                      <Link href={`/clinics/${item.clinic_id}`} className="block font-bold">{item.clinic_name}</Link>
                      <Link href={`/services/${item.service_id}`} className="mt-1 block text-sm text-[var(--muted-foreground)]">{item.display_service_name || item.service_name}</Link>
                    </div>
                    <div className="whitespace-nowrap text-lg font-bold">{formatPrice(item.price, item.currency, locale)}</div>
                  </div>
                  <div className="mt-4">
                    <MapLinks
                      providerName={item.clinic_name}
                      city={item.city}
                      address={item.address}
                      latitude={item.latitude}
                      longitude={item.longitude}
                      compact
                    />
                  </div>
                  <div className="mt-4 flex flex-wrap items-center justify-between gap-3">
                    <FreshnessBadge state={item.freshness_state} ageDays={item.freshness_age_days} />
                    {item.source_url ? <Link href={item.source_url} target="_blank" rel="noreferrer" className="text-xs font-bold text-[var(--primary)]">{t("publicSource")}</Link> : null}
                  </div>
                </Card>
              );
            })}
          </div>
        </>
      ) : (
        <EmptyState title={t("noComparison")} message={t("noComparisonText")} queries={suggestions} target="/compare" />
      )}
    </div>
  );
}

function CompareFilterForm({
  initialValues,
  locked,
  onApply,
}: {
  initialValues: { q: string; city: string; category: string; sort: CompareSort };
  locked: boolean;
  onApply: (values: { q: string; city: string; category: string; sort: CompareSort }) => void;
}) {
  const { t } = useI18n();
  const [values, setValues] = useState(initialValues);

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    onApply(values);
  }

  return (
    <form onSubmit={submit} className="grid gap-3 md:grid-cols-4 md:items-end">
      <Field label={t("service")}>
        <Input value={values.q} onChange={(event) => setValues({ ...values, q: event.target.value })} placeholder={t("searchPlaceholder")} disabled={locked} />
      </Field>
      <Field label={t("city")}>
        <Input value={values.city} onChange={(event) => setValues({ ...values, city: event.target.value })} placeholder="Astana" />
      </Field>
      <Field label={t("category")}>
        <Input value={values.category} onChange={(event) => setValues({ ...values, category: event.target.value })} placeholder="МРТ, УЗИ" />
      </Field>
      <Field label={t("sort")}>
        <select value={values.sort} onChange={(event) => setValues({ ...values, sort: event.target.value as CompareSort })} className="h-10 w-full rounded-md border border-[var(--border)] bg-[var(--surface)] px-3 text-sm outline-none focus:border-[var(--primary)]">
          <option value="price_asc">{t("priceAsc")}</option>
          <option value="price_desc">{t("priceDesc")}</option>
          <option value="updated_desc">{t("updatedDesc")}</option>
        </select>
      </Field>
      <Button type="submit" className="md:col-span-4">{t("comparePrices")}</Button>
    </form>
  );
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return <label className="space-y-1.5 text-xs font-semibold text-[var(--muted-foreground)]"><span>{label}</span>{children}</label>;
}

function toSort(value: string | null): CompareSort {
  return value === "price_desc" || value === "updated_desc" ? value : "price_asc";
}
