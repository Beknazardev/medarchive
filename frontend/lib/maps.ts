type MapQueryInput = {
  providerName?: string;
  city?: string;
  address?: string;
};

type MapLinksInput = MapQueryInput & {
  latitude?: number | null;
  longitude?: number | null;
};

type MapLinks = {
  query: string;
  twoGis: string;
  googleMaps: string;
  yandexMaps: string;
};

export function buildMapQuery({ providerName, city, address }: MapQueryInput): string {
  const parts: string[] = [];
  if (providerName) parts.push(providerName);
  if (city) parts.push(city);
  if (address) parts.push(address);
  return parts.join(", ");
}

export function buildMapLinks({ providerName, city, address, latitude, longitude }: MapLinksInput): MapLinks {
  const query = buildMapQuery({ providerName, city, address });
  const hasCoords = latitude != null && longitude != null;

  const twoGis = `https://2gis.kz/search/${encodeURIComponent(query)}`;

  let googleMaps: string;
  if (hasCoords) {
    googleMaps = `https://www.google.com/maps/search/?api=1&query=${latitude},${longitude}`;
  } else {
    googleMaps = `https://www.google.com/maps/search/?api=1&query=${encodeURIComponent(query)}`;
  }

  let yandexMaps: string;
  if (hasCoords) {
    yandexMaps = `https://yandex.kz/maps/?ll=${longitude},${latitude}&pt=${longitude},${latitude},pm2rdm&text=${encodeURIComponent(query)}`;
  } else {
    yandexMaps = `https://yandex.kz/maps/?text=${encodeURIComponent(query)}`;
  }

  return { query, twoGis, googleMaps, yandexMaps };
}
