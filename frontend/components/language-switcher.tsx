"use client";

import { useI18n } from "@/components/i18n-provider";
import { locales } from "@/lib/i18n";
import { cn } from "@/lib/utils";

export function LanguageSwitcher() {
  const { locale, setLocale } = useI18n();

  return (
    <div className="flex h-9 items-center rounded-md border border-[var(--border)] bg-[var(--surface-muted)] p-0.5" aria-label="Language">
      {locales.map((item) => (
        <button
          key={item}
          type="button"
          onClick={() => setLocale(item)}
          className={cn(
            "h-7 min-w-9 rounded px-2 text-[11px] font-bold uppercase transition-colors",
            locale === item
              ? "bg-[var(--surface)] text-[var(--foreground)] shadow-sm"
              : "text-[var(--muted-foreground)] hover:text-[var(--foreground)]",
          )}
          aria-pressed={locale === item}
        >
          {item === "kk" ? "KZ" : item.toUpperCase()}
        </button>
      ))}
    </div>
  );
}
