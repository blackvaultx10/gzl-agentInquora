export type CurrencyCode = "CNY" | "USD";
export type ExportFormat = "xlsx" | "docx";
export type InquiryJobStatus = "queued" | "processing" | "completed" | "failed";

export interface ParsedDocument {
  filename: string;
  file_type: string;
  parser: string;
  document_role: "legend" | "spec" | "system" | "plan" | "other";
  text_excerpt: string;
  warnings: string[];
}

export interface InquiryItem {
  boq_code?: string | null;
  name: string;
  category?: string | null;
  specification?: string | null;
  material?: string | null;
  quantity: number;
  unit: string;
  inquiry_method?: string | null;
  source_documents: string[];
  source_snippet: string;
  confidence: number;
  vendor?: string | null;
  currency: CurrencyCode;
  unit_price?: number | null;
  total_price?: number | null;
  price_basis?: string | null;
  match_score?: number | null;
  reference_vendor?: string | null;
  reference_unit_price?: number | null;
  reference_total_price?: number | null;
  reference_basis?: string | null;
  reference_match_score?: number | null;
  price_source?: string | null;
  anomalies: string[];
}

export interface InquirySummary {
  item_count: number;
  reference_count: number;
  pending_count: number;
  flagged_count: number;
  reference_subtotal: number;
  currency: CurrencyCode;
}

export interface InquiryResult {
  request_id: string;
  project_name: string;
  created_at: string;
  extraction_mode: "openai" | "deepseek" | "heuristic";
  pricing_mode: "reference_only" | "supplier_quote";
  documents: ParsedDocument[];
  items: InquiryItem[];
  warnings: string[];
  summary: InquirySummary;
}

export interface ProjectSummary {
  id: number;
  name: string;
  description?: string | null;
  created_at: string;
  updated_at: string;
  last_processed_at?: string | null;
}

export interface InquiryJobProgress {
  step: string;
  current: number;
  total: number;
  percent: number;
  current_file_name?: string | null;
}

export interface InquiryJobSnapshot {
  job_id: string;
  status: InquiryJobStatus;
  project_id: number;
  project_name: string;
  created_at: string;
  updated_at: string;
  progress: InquiryJobProgress;
  result?: InquiryResult | null;
  error?: string | null;
}

export interface ProviderConfig {
  id: number;
  provider_type: string;
  name: string;
  api_key?: string | null;
  secret_key?: string | null;
  base_url?: string | null;
  model?: string | null;
  extra_config?: string | null;
  is_active: boolean;
  has_secret_key?: boolean;
  created_at: string;
  updated_at: string;
}
