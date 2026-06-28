"use client";

import { createContext, useContext, useEffect, useMemo, useSyncExternalStore } from "react";

import { dictionaries, locales, type Locale, type TranslationKey } from "@/lib/i18n";

type I18nContextValue = {
  locale: Locale;
  setLocale: (locale: Locale) => void;
  t: (key: TranslationKey) => string;
};

const I18nContext = createContext<I18nContextValue | null>(null);

export function I18nProvider({ children }: { children: React.ReactNode }) {
  const locale = useSyncExternalStore<Locale>(subscribe, getLocaleSnapshot, () => "ru");

  function setLocale(nextLocale: Locale) {
    window.localStorage.setItem("medprice-locale", nextLocale);
    window.dispatchEvent(new Event("medprice-locale-change"));
  }

  useEffect(() => {
    document.documentElement.lang = locale;
  }, [locale]);

  const value = useMemo<I18nContextValue>(
    () => ({ locale, setLocale, t: (key) => dictionaries[locale][key] }),
    [locale],
  );

  return <I18nContext.Provider value={value}>{children}</I18nContext.Provider>;
}

function subscribe(callback: () => void) {
  window.addEventListener("storage", callback);
  window.addEventListener("medprice-locale-change", callback);
  return () => {
    window.removeEventListener("storage", callback);
    window.removeEventListener("medprice-locale-change", callback);
  };
}

function getLocaleSnapshot(): Locale {
  const stored = window.localStorage.getItem("medprice-locale");
  return stored && locales.includes(stored as Locale) ? stored as Locale : "ru";
}

export function useI18n() {
  const context = useContext(I18nContext);
  if (!context) {
    throw new Error("useI18n must be used within I18nProvider");
  }
  return context;
}
