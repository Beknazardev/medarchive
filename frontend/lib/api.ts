import type {
  ApiError,
  ClinicDetailsResponse,
  ComparePricesResponse,
  ImportPricesRequest,
  ImportPricesResponse,
  SearchServicesResponse,
  ServiceDetailsResponse,
} from "@/lib/types";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

export class ApiClientError extends Error {
  code: string;
  status: number;
  details: unknown[];

  constructor(message: string, code: string, status: number, details: unknown[] = []) {
    super(message);
    this.name = "ApiClientError";
    this.code = code;
    this.status = status;
    this.details = details;
  }
}

type QueryValue = string | number | null | undefined;
type RequestOptions = {
  method?: "GET" | "POST";
  params?: Record<string, QueryValue>;
  body?: unknown;
  headers?: Record<string, string>;
};

function buildUrl(path: string, params?: Record<string, QueryValue>) {
  const url = new URL(path, API_BASE_URL);

  Object.entries(params ?? {}).forEach(([key, value]) => {
    if (value !== null && value !== undefined && value !== "") {
      url.searchParams.set(key, String(value));
    }
  });

  return url.toString();
}

async function request<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const response = await fetch(buildUrl(path, options.params), {
    method: options.method ?? "GET",
    headers: {
      Accept: "application/json",
      ...options.headers,
    },
    body: options.body === undefined ? undefined : JSON.stringify(options.body),
    cache: "no-store",
  });

  const payload = (await response.json().catch(() => null)) as T | ApiError | null;

  if (!response.ok) {
    const apiError = payload as ApiError | null;
    throw new ApiClientError(
      apiError?.error.message ?? "Запрос не выполнен",
      apiError?.error.code ?? "HTTP_ERROR",
      response.status,
      apiError?.error.details ?? [],
    );
  }

  return payload as T;
}

export type SearchParams = {
  q: string;
  city?: string;
  category?: string;
  min_price?: number;
  max_price?: number;
  sort?: "relevance" | "price_asc" | "price_desc" | "updated_desc";
  limit?: number;
  offset?: number;
};

export type CityItem = {
  name: string;
  aliases: string[];
};

export type CitiesResponse = {
  data: CityItem[];
};

export function searchServices(params: SearchParams) {
  return request<SearchServicesResponse>("/api/v1/services/search", { params });
}

export function getCities() {
  return request<CitiesResponse>("/api/v1/cities");
}

export function getClinic(id: string | number) {
  return request<ClinicDetailsResponse>(`/api/v1/clinics/${id}`);
}

export function getService(id: string | number) {
  return request<ServiceDetailsResponse>(`/api/v1/services/${id}`);
}

export function comparePrices(params: {
  q?: string;
  service_id?: number;
  normalized_service_id?: number;
  city?: string;
  category?: string;
  sort?: "price_asc" | "price_desc" | "updated_desc";
}) {
  return request<ComparePricesResponse>("/api/v1/prices/compare", { params });
}

export function importPrices(payload: ImportPricesRequest, apiKey: string) {
  return request<ImportPricesResponse>("/api/v1/import/prices", {
    method: "POST",
    body: payload,
    headers: {
      "Content-Type": "application/json",
      "X-API-Key": apiKey,
    },
  });
}
