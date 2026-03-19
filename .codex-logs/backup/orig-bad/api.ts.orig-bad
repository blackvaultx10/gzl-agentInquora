import type { ExportFormat, InquiryResult, ProviderConfig } from "@/lib/types";

const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "/api";

async function ensureOk(response: Response) {
  if (response.ok) {
    return;
  }

  let message = "请求失败";
  try {
    const payload = (await response.json()) as { detail?: string };
    message = payload.detail ?? message;
  } catch {
    message = response.statusText || message;
  }

  throw new Error(message);
}

// 配置管理 API
export async function getConfigs(): Promise<ProviderConfig[]> {
  const response = await fetch(`${API_BASE_URL}/configs`);
  await ensureOk(response);
  return (await response.json()) as ProviderConfig[];
}

export async function getConfig(providerType: string): Promise<ProviderConfig & { api_key?: string; secret_key?: string }> {
  const response = await fetch(`${API_BASE_URL}/configs/${providerType}`);
  await ensureOk(response);
  return (await response.json()) as ProviderConfig & { api_key?: string; secret_key?: string };
}

export async function createConfig(config: Omit<ProviderConfig, "id" | "created_at" | "updated_at">): Promise<ProviderConfig> {
  const response = await fetch(`${API_BASE_URL}/configs`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(config),
  });
  await ensureOk(response);
  return (await response.json()) as ProviderConfig;
}

export async function updateConfig(providerType: string, config: Omit<ProviderConfig, "id" | "created_at" | "updated_at">): Promise<ProviderConfig> {
  const response = await fetch(`${API_BASE_URL}/configs/${providerType}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(config),
  });
  await ensureOk(response);
  return (await response.json()) as ProviderConfig;
}

export async function deleteConfig(providerType: string): Promise<void> {
  const response = await fetch(`${API_BASE_URL}/configs/${providerType}`, {
    method: "DELETE",
  });
  await ensureOk(response);
}

export async function getProviderTypes(): Promise<Array<{ type: string; name: string; description: string; fields: string[] }>> {
  const response = await fetch(`${API_BASE_URL}/configs/providers`);
  await ensureOk(response);
  return (await response.json()) as Array<{ type: string; name: string; description: string; fields: string[] }>;
}

export async function parseInquiry(files: File[], maxPages?: number): Promise<InquiryResult> {
  const formData = new FormData();
  files.forEach((file) => formData.append("files", file));

  const url = maxPages ? `${API_BASE_URL}/inquiry/parse?max_pages=${maxPages}` : `${API_BASE_URL}/inquiry/parse`;

  const response = await fetch(url, {
    method: "POST",
    body: formData,
  });
  await ensureOk(response);
  return (await response.json()) as InquiryResult;
}

export async function exportInquiry(
  result: InquiryResult,
  format: ExportFormat,
): Promise<Blob> {
  const response = await fetch(`${API_BASE_URL}/inquiry/export?format=${format}`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ result }),
  });
  await ensureOk(response);
  return response.blob();
}

