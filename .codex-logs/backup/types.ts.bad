export type CurrencyCode = "CNY" | "USD";
export type ExportFormat = "xlsx" | "docx";

export interface ParsedDocument {
  filename: string;
  file_type: string;
  parser: string;
  text_excerpt: string;
  warnings: string[];
}

export interface InquiryItem {
  name: string;
  category?: string | null;
  specification?: string | null;
  material?: string | null;
  quantity: number;
  unit: string;
  source_snippet: string;
  confidence: number;
  vendor?: string | null;
  currency: CurrencyCode;
  unit_price?: number | null;
  total_price?: number | null;
  price_basis?: string | null;
  match_score?: number | null;
  anomalies: string[];
}

export interface InquirySummary {
  item_count: number;
  matched_count: number;
  flagged_count: number;
  subtotal: number;
  currency: CurrencyCode;
}

export interface InquiryResult {
  request_id: string;
  created_at: string;
  extraction_mode: "openai" | "heuristic";
  documents: ParsedDocument[];
  items: InquiryItem[];
  warnings: string[];
  summary: InquirySummary;
}

// 第三方服务提供商配置
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

