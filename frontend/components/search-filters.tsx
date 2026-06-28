"use client";

import { FormEvent, useEffect, useRef, useState } from "react";
import { Filter, RotateCcw } from "lucide-react";

import { useI18n } from "@/components/i18n-provider";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { getCities, type CityItem } from "@/lib/api";

export type SearchFilterValues = {
  city: string;
  category: string;
  minPrice: string;
  maxPrice: string;
  sort: "relevance" | "price_asc" | "price_desc" | "updated_desc";
};

export function SearchFilters({
  initialValues,
  onApply,
  onClear,
}: {
  initialValues: SearchFilterValues;
  onApply: (values: SearchFilterValues) => void;
  onClear: () => void;
}) {
  const { t } = useI18n();
  const [values, setValues] = useState(initialValues);
  const [cities, setCities] = useState<CityItem[]>([]);
  const [cityQuery, setCityQuery] = useState(initialValues.city);
  const [showCityDropdown, setShowCityDropdown] = useState(false);
  const cityDropdownRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    getCities()
      .then((res) => setCities(res.data))
      .catch(() => {});
  }, []);

  useEffect(() => {
    setCityQuery(initialValues.city);
  }, [initialValues.city]);

  useEffect(() => {
    function handleClickOutside(e: MouseEvent) {
      if (cityDropdownRef.current && !cityDropdownRef.current.contains(e.target as Node)) {
        setShowCityDropdown(false);
      }
    }
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  const filteredCities = cities.filter((c) => {
    const q = cityQuery.toLowerCase().trim();
    if (!q) return true;
    return (
      c.name.toLowerCase().includes(q) ||
      c.aliases.some((a) => a.toLowerCase().includes(q))
    );
  });

  function selectCity(city: string) {
    setCityQuery(city);
    setValues({ ...values, city });
    setShowCityDropdown(false);
  }

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    onApply({ ...values, city: cityQuery });
  }

  return (
    <Card className="p-4 shadow-none">
      <form onSubmit={submit}>
        <div className="mb-4 flex items-center gap-2 text-sm font-semibold">
          <Filter className="h-4 w-4 text-[var(--primary)]" />
          {t("filters")}
        </div>
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-5">
          <div className="space-y-1.5" ref={cityDropdownRef}>
            <label className="text-xs font-semibold text-[var(--muted-foreground)]">
              {t("city")}
            </label>
            <div className="relative">
              <Input
                value={cityQuery}
                onChange={(event) => {
                  setCityQuery(event.target.value);
                  setShowCityDropdown(true);
                  setValues({ ...values, city: event.target.value });
                }}
                onFocus={() => setShowCityDropdown(true)}
                placeholder={t("city")}
                autoComplete="off"
              />
              {showCityDropdown && filteredCities.length > 0 && (
                <div className="absolute z-50 mt-1 max-h-48 w-full overflow-auto rounded-md border border-[var(--border)] bg-[var(--surface)] shadow-md">
                  {filteredCities.map((city) => (
                    <button
                      key={city.name}
                      type="button"
                      className="flex w-full items-center justify-between px-3 py-2 text-sm hover:bg-[var(--accent)]"
                      onClick={() => selectCity(city.name)}
                    >
                      <span>{city.name}</span>
                      {city.aliases.length > 0 && (
                        <span className="text-[var(--muted-foreground)] text-xs">
                          {city.aliases.slice(0, 2).join(", ")}
                        </span>
                      )}
                    </button>
                  ))}
                </div>
              )}
            </div>
          </div>
          <Field label={t("category")}>
            <Input value={values.category} onChange={(event) => setValues({ ...values, category: event.target.value })} placeholder="МРТ, УЗИ" />
          </Field>
          <Field label={t("minPrice")}>
            <Input type="number" min={0} value={values.minPrice} onChange={(event) => setValues({ ...values, minPrice: event.target.value })} placeholder="0" />
          </Field>
          <Field label={t("maxPrice")}>
            <Input type="number" min={0} value={values.maxPrice} onChange={(event) => setValues({ ...values, maxPrice: event.target.value })} placeholder="50 000" />
          </Field>
          <Field label={t("sort")}>
            <select
              value={values.sort}
              onChange={(event) => setValues({ ...values, sort: event.target.value as SearchFilterValues["sort"] })}
              className="h-10 w-full rounded-md border border-[var(--border)] bg-[var(--surface)] px-3 text-sm outline-none focus:border-[var(--primary)] focus:ring-2 focus:ring-[var(--primary-soft)]"
            >
              <option value="relevance">{t("relevance")}</option>
              <option value="price_asc">{t("priceAsc")}</option>
              <option value="price_desc">{t("priceDesc")}</option>
              <option value="updated_desc">{t("updatedDesc")}</option>
            </select>
          </Field>
        </div>
        <div className="mt-4 flex gap-2">
          <Button type="submit">{t("apply")}</Button>
          <Button type="button" variant="ghost" onClick={onClear}>
            <RotateCcw className="mr-2 h-4 w-4" />
            {t("clear")}
          </Button>
        </div>
      </form>
    </Card>
  );
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <label className="space-y-1.5 text-xs font-semibold text-[var(--muted-foreground)]">
      <span>{label}</span>
      {children}
    </label>
  );
}
