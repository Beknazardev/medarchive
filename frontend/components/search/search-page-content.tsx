"use client";

import { useEffect, useMemo, useState } from "react";
import { usePathname, useRouter, useSearchParams } from "next/navigation";

import { useI18n } from "@/components/i18n-provider";
import { PriceCard } from "@/components/price-card";
import { SearchFilters, type SearchFilterValues } from "@/components/search-filters";
import { SearchBox } from "@/components/search/search-box";
import { EmptyState } from "@/components/states/empty-state";
import { ErrorState } from "@/components/states/error-state";
import { LoadingState } from "@/components/states/loading-state";
import { Button } from "@/components/ui/button";
import { searchServices } from "@/lib/api";
import type { SearchServicesResponse } from "@/lib/types";

const DEFAULT_LIMIT = 10;
type SearchState = { key: string; data: SearchServicesResponse | null; error: boolean };

export function SearchPageContent() {
  const { locale, t } = useI18n();
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const q = searchParams.get("q") ?? "";
  const city = searchParams.get("city") ?? "";
  const category = searchParams.get("category") ?? "";
  const minPrice = searchParams.get("min_price") ?? "";
  const maxPrice = searchParams.get("max_price") ?? "";
  const sort = toSort(searchParams.get("sort"));
  const limit = toPositiveNumber(searchParams.get("limit"), DEFAULT_LIMIT);
  const offset = toNonNegativeNumber(searchParams.get("offset"), 0);
  const [state, setState] = useState<SearchState>({ key: "", data: null, error: false });
  const requestKey = q.trim() ? [q.trim(), city, category, minPrice, maxPrice, sort, limit, offset].join("|") : "";

  useEffect(() => {
    if (!requestKey) return;
    let active = true;
    searchServices({
      q: q.trim(),
      city,
      category,
      min_price: minPrice ? Number(minPrice) : undefined,
      max_price: maxPrice ? Number(maxPrice) : undefined,
      sort,
      limit,
      offset,
    })
      .then((data) => active && setState({ key: requestKey, data, error: false }))
      .catch(() => active && setState({ key: requestKey, data: null, error: true }));
    return () => { active = false; };
  }, [requestKey, q, city, category, minPrice, maxPrice, sort, limit, offset]);

  const data = state.key === requestKey ? state.data : null;
  const error = state.key === requestKey && state.error;
  const loading = Boolean(requestKey) && state.key !== requestKey;
  const total = data?.meta.total ?? 0;
  const pageLabel = useMemo(() => total ? `${offset + 1}–${Math.min(offset + limit, total)} / ${total}` : `0 ${t("results")}`, [limit, offset, t, total]);
  const suggestions = locale === "en" ? ["PCR", "ultrasound", "MRI", "consultation"] : locale === "kk" ? ["ПТР", "УДЗ", "МРТ", "терапевт қабылдауы"] : ["ПЦР", "УЗИ", "МРТ", "терапевт"];

  function pushParams(next: Record<string, string | number | undefined>) {
    const params = new URLSearchParams(searchParams.toString());
    Object.entries(next).forEach(([key, value]) => value === undefined || value === "" ? params.delete(key) : params.set(key, String(value)));
    router.push(`${pathname}?${params.toString()}`);
  }

  return (
    <div className="space-y-6">
      <header className="max-w-3xl">
        <h1 className="text-3xl font-bold sm:text-4xl">{t("searchTitle")}</h1>
        <p className="mt-2 text-sm leading-6 text-[var(--muted-foreground)]">{t("searchDescription")}</p>
      </header>
      <SearchBox key={q} initialQuery={q} prominent />
      <SearchFilters
        key={[city, category, minPrice, maxPrice, sort].join("|")}
        initialValues={{ city, category, minPrice, maxPrice, sort }}
        onApply={(filters) => pushParams({ city: filters.city.trim(), category: filters.category.trim(), min_price: filters.minPrice, max_price: filters.maxPrice, sort: filters.sort, offset: 0 })}
        onClear={() => pushParams({ city: undefined, category: undefined, min_price: undefined, max_price: undefined, sort: undefined, offset: 0 })}
      />

      {!q.trim() ? (
        <EmptyState title={t("enterService")} message={t("enterServiceText")} queries={suggestions} />
      ) : loading ? (
        <LoadingState label={t("searchLoading")} />
      ) : error ? (
        <ErrorState title={t("searchError")} message={t("backendError")} />
      ) : data && data.data.length > 0 ? (
        <section className="space-y-4">
          <div className="flex items-center justify-between">
            <p className="text-sm font-semibold text-[var(--muted-foreground)]">{pageLabel}</p>
            <div className="flex gap-2">
              <Button variant="secondary" disabled={offset === 0} onClick={() => pushParams({ offset: Math.max(0, offset - limit) })}>{t("previous")}</Button>
              <Button variant="secondary" disabled={offset + limit >= total} onClick={() => pushParams({ offset: offset + limit })}>{t("next")}</Button>
            </div>
          </div>
          <div className="space-y-4">
            {data.data.map((item) => <PriceCard key={`${item.service_id}-${item.clinic.id}-${item.branch.id}`} item={item} />)}
          </div>
        </section>
      ) : (
        <EmptyState title={t("noResults")} message={t("noResultsText")} queries={suggestions} />
      )}
    </div>
  );
}

function toSort(value: string | null): SearchFilterValues["sort"] {
  return value === "price_asc" || value === "price_desc" || value === "updated_desc" ? value : "relevance";
}

function toPositiveNumber(value: string | null, fallback: number) {
  const parsed = Number(value);
  return Number.isFinite(parsed) && parsed > 0 ? parsed : fallback;
}

function toNonNegativeNumber(value: string | null, fallback: number) {
  const parsed = Number(value);
  return Number.isFinite(parsed) && parsed >= 0 ? parsed : fallback;
}
