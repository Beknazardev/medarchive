"use client";

import { FormEvent, useState } from "react";
import { useRouter } from "next/navigation";
import { Search } from "lucide-react";

import { useI18n } from "@/components/i18n-provider";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";

export function SearchBox({
  initialQuery = "",
  target = "/search",
  prominent = false,
}: {
  initialQuery?: string;
  target?: "/search" | "/compare";
  prominent?: boolean;
}) {
  const router = useRouter();
  const { t } = useI18n();
  const [query, setQuery] = useState(initialQuery);

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const value = query.trim();
    if (value) router.push(`${target}?q=${encodeURIComponent(value)}`);
  }

  return (
    <form onSubmit={handleSubmit} className="flex w-full flex-col gap-2 sm:flex-row">
      <div className="relative flex-1">
        <Search className="pointer-events-none absolute left-3.5 top-1/2 h-5 w-5 -translate-y-1/2 text-[var(--muted-foreground)]" />
        <Input
          value={query}
          onChange={(event) => setQuery(event.target.value)}
          className={prominent ? "h-12 pl-11 text-base" : "pl-10"}
          placeholder={t("searchPlaceholder")}
          aria-label={t("searchPrices")}
        />
      </div>
      <Button type="submit" className={prominent ? "h-12 px-6" : ""}>
        <Search className="mr-2 h-4 w-4" aria-hidden="true" />
        {target === "/compare" ? t("comparePrices") : t("searchPrices")}
      </Button>
    </form>
  );
}
