export type PaginationMeta = {
  limit: number;
  offset: number;
  total: number;
};

export type ApiError = {
  error: {
    code: string;
    message: string;
    details: unknown[];
  };
};

export type FreshnessState = "fresh" | "aging" | "stale" | "unknown";

export type ImportClinicPayload = {
  external_id: string;
  name: string;
  legal_name?: string;
  city: string;
  address?: string;
  phone?: string;
  website?: string;
};

export type ImportBranchPayload = {
  external_id?: string;
  name?: string;
  city?: string;
  address?: string;
  phone?: string;
  latitude?: number;
  longitude?: number;
};

export type ImportServicePayload = {
  external_id?: string;
  name: string;
  category: string;
  description?: string;
  price: number;
  currency: string;
  updated_at: string;
  source_url?: string;
  parsed_at?: string;
  duration_minutes?: number;
  is_available?: boolean;
};

export type ImportPricesRequest = {
  source: string;
  source_type?: string;
  source_url?: string;
  robots_policy_notes?: string;
  crawl_delay_seconds?: number;
  source_batch_id?: string;
  clinic: ImportClinicPayload;
  branch?: ImportBranchPayload;
  services: ImportServicePayload[];
};

export type ImportErrorItem = {
  index: number;
  external_id: string | null;
  code: string;
  message: string;
  field: string | null;
};

export type ImportPricesResponse = {
  data: {
    batch_id: number;
    status: string;
    source: string;
    clinic_id: number;
    branch_id: number;
    received_count: number;
    created_count: number;
    updated_count: number;
    unchanged_count: number;
    error_count: number;
    errors: ImportErrorItem[];
  };
};

export type SearchServiceItem = {
  service_id: number;
  service_name: string;
  display_service_name: string;
  normalized_service_id: number;
  normalized_service_name: string;
  display_category_name: string;
  category: string;
  clinic: {
    id: number;
    name: string;
  };
  branch: {
    id: number;
    address: string;
    city: string;
    latitude?: number | null;
    longitude?: number | null;
  };
  price: {
    amount: string;
    currency: string;
    updated_at: string;
    source_url: string | null;
    parsed_at: string;
    freshness_state: FreshnessState;
    freshness_age_days: number | null;
  };
  source_language?: string | null;
  locale_used?: string | null;
};

export type SearchServicesResponse = {
  data: SearchServiceItem[];
  meta: PaginationMeta;
};

export type ClinicDetailsResponse = {
  data: {
    id: number;
    name: string;
    city: string;
    phone: string | null;
    website: string | null;
    branches: Array<{
      id: number;
      name: string | null;
      city: string;
      address: string;
      phone: string | null;
      latitude?: number | null;
      longitude?: number | null;
    }>;
    services: Array<{
      service_id: number;
      name: string;
      category: string;
      price: string;
      currency: string;
      updated_at: string;
      source_url: string | null;
      parsed_at: string;
      freshness_state: FreshnessState;
      freshness_age_days: number | null;
    }>;
  };
};

export type ServiceDetailsResponse = {
  data: {
    id: number;
    name: string;
    normalized_service: {
      id: number;
      name: string;
    };
    category: {
      id: number;
      name: string;
    };
    prices: Array<{
      clinic_id: number;
      clinic_name: string;
      branch_id: number;
      city: string;
      address: string;
      latitude?: number | null;
      longitude?: number | null;
      amount: string;
      currency: string;
      updated_at: string;
      source_url: string | null;
      parsed_at: string;
      freshness_state: FreshnessState;
      freshness_age_days: number | null;
    }>;
    stats: {
      min_price: string | null;
      max_price: string | null;
      average_price: string | null;
      count: number;
    };
  };
};

export type ComparePricesResponse = {
  data: {
    query: {
      service_id: number | null;
      normalized_service_id: number | null;
      q: string | null;
      city: string | null;
      category: string | null;
    };
    stats: {
      min_price: string | null;
      max_price: string | null;
      average_price: string | null;
      count: number;
      currency: string | null;
    };
    items: Array<{
      clinic_id: number;
      clinic_name: string;
      branch_id: number;
      city: string;
      address: string;
      latitude?: number | null;
      longitude?: number | null;
      service_id: number;
      service_name: string;
      display_service_name: string;
      display_category_name: string;
      price: string;
      currency: string;
      updated_at: string;
      source_url: string | null;
      parsed_at: string;
      freshness_state: FreshnessState;
      freshness_age_days: number | null;
    }>;
  };
};
