"use client";

import Link from "next/link";
import { Activity, GitCompareArrows, Search, Upload } from "lucide-react";

import { useI18n } from "@/components/i18n-provider";
import { LanguageSwitcher } from "@/components/language-switcher";
import { Container } from "@/components/layout/container";
import { ThemeToggle } from "@/components/theme-toggle";

export function SiteHeader() {
  const { t } = useI18n();
  const navItems = [
    { href: "/search", label: t("navSearch"), icon: Search },
    { href: "/compare", label: t("navCompare"), icon: GitCompareArrows },
    { href: "/admin/import", label: t("navImport"), icon: Upload },
  ];

  return (
    <header className="sticky top-0 z-40 border-b border-[var(--border)] bg-[color:var(--surface)]/95 backdrop-blur">
      <Container className="flex min-h-16 items-center justify-between gap-3">
        <Link href="/" className="flex min-w-0 items-center gap-2.5 font-bold">
          <span className="flex h-9 w-9 flex-none items-center justify-center rounded-md bg-[var(--primary)] text-[var(--primary-foreground)]">
            <Activity className="h-5 w-5" aria-hidden="true" />
          </span>
          <span className="truncate text-[15px] sm:text-base">MedServicePrice.kz</span>
        </Link>

        <div className="flex items-center gap-1.5 sm:gap-2">
          <nav className="hidden items-center gap-1 md:flex">
            {navItems.map(({ href, label, icon: Icon }) => (
              <Link
                key={href}
                href={href}
                className="inline-flex h-9 items-center gap-2 rounded-md px-3 text-sm font-medium text-[var(--muted-foreground)] transition-colors hover:bg-[var(--surface-muted)] hover:text-[var(--foreground)]"
              >
                <Icon className="h-4 w-4" aria-hidden="true" />
                {label}
              </Link>
            ))}
          </nav>
          <LanguageSwitcher />
          <ThemeToggle />
        </div>
      </Container>

      <nav className="border-t border-[var(--border)] md:hidden">
        <Container className="grid grid-cols-3 p-1.5">
          {navItems.map(({ href, label, icon: Icon }) => (
            <Link
              key={href}
              href={href}
              className="flex h-10 items-center justify-center gap-1.5 rounded-md text-xs font-semibold text-[var(--muted-foreground)] hover:bg-[var(--surface-muted)] hover:text-[var(--foreground)]"
            >
              <Icon className="h-4 w-4" aria-hidden="true" />
              {label}
            </Link>
          ))}
        </Container>
      </nav>
    </header>
  );
}
