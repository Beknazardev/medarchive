"use client";

import { MapPin, ExternalLink } from "lucide-react";

import { useI18n } from "@/components/i18n-provider";
import { buildMapLinks } from "@/lib/maps";

type MapLinksProps = {
  providerName?: string;
  city?: string;
  address?: string;
  latitude?: number | null;
  longitude?: number | null;
  compact?: boolean;
};

export function MapLinks({ providerName, city, address, latitude, longitude, compact = false }: MapLinksProps) {
  const { t } = useI18n();
  const links = buildMapLinks({ providerName, city, address, latitude, longitude });

  const displayText = address ? `${city ? city + ", " : ""}${address}` : city || providerName;

  if (compact) {
    return (
      <div className="flex flex-wrap items-center gap-2 text-sm">
        <span className="inline-flex items-center gap-1.5 text-[var(--muted-foreground)]">
          <MapPin className="h-3.5 w-3.5 flex-none" />
          {displayText}
        </span>
        <span className="flex gap-1">
          <MapLink href={links.twoGis} label="2GIS" />
          <MapLink href={links.googleMaps} label="Google" />
          <MapLink href={links.yandexMaps} label="Yandex" />
        </span>
      </div>
    );
  }

  return (
    <div className="space-y-2">
      <div className="flex items-center gap-2 text-sm text-[var(--muted-foreground)]">
        <MapPin className="h-4 w-4 flex-none" />
        <span>{displayText}</span>
      </div>
      <div className="flex flex-wrap gap-2">
        <MapButton href={links.twoGis} label="2GIS" />
        <MapButton href={links.googleMaps} label="Google Maps" />
        <MapButton href={links.yandexMaps} label="Yandex Maps" />
      </div>
    </div>
  );
}

function MapLink({ href, label }: { href: string; label: string }) {
  return (
    <a
      href={href}
      target="_blank"
      rel="noreferrer"
      className="inline-flex items-center gap-1 rounded border border-[var(--border)] px-2 py-0.5 text-xs font-medium text-[var(--muted-foreground)] hover:border-[var(--primary)] hover:text-[var(--primary)]"
    >
      {label}
      <ExternalLink className="h-3 w-3" />
    </a>
  );
}

function MapButton({ href, label }: { href: string; label: string }) {
  return (
    <a
      href={href}
      target="_blank"
      rel="noreferrer"
      className="inline-flex items-center gap-1.5 rounded-md border border-[var(--border)] bg-[var(--surface)] px-3 py-1.5 text-xs font-semibold text-[var(--muted-foreground)] hover:border-[var(--primary)] hover:text-[var(--primary)]"
    >
      <MapPin className="h-3 w-3" />
      {label}
      <ExternalLink className="h-3 w-3" />
    </a>
  );
}
