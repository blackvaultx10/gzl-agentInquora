import type {
  ExportFormat,
  InquiryJobSnapshot,
  InquiryResult,
  ProjectSummary,
  ProviderConfig,
} from "@/lib/types";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "/api";

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

export async function getConfigs(): Promise<ProviderConfig[]> {
  const response = await fetch(`${API_BASE_URL}/configs`);
  await ensureOk(response);
  return (await response.json()) as ProviderConfig[];
}

export async function getConfig(
  providerType: string,
): Promise<ProviderConfig & { api_key?: string; secret_key?: string }> {
  const response = await fetch(`${API_BASE_URL}/configs/${providerType}`);
  await ensureOk(response);
  return (await response.json()) as ProviderConfig & {
    api_key?: string;
    secret_key?: string;
  };
}

export async function createConfig(
  config: Omit<ProviderConfig, "id" | "created_at" | "updated_at">,
): Promise<ProviderConfig> {
  const response = await fetch(`${API_BASE_URL}/configs`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(config),
  });
  await ensureOk(response);
  return (await response.json()) as ProviderConfig;
}

export async function updateConfig(
  providerType: string,
  config: Omit<ProviderConfig, "id" | "created_at" | "updated_at">,
): Promise<ProviderConfig> {
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

export async function getProviderTypes(): Promise<
  Array<{ type: string; name: string; description: string; fields: string[] }>
> {
  const response = await fetch(`${API_BASE_URL}/configs/providers`);
  await ensureOk(response);
  return (await response.json()) as Array<{
    type: string;
    name: string;
    description: string;
    fields: string[];
  }>;
}

export async function parseInquiry(
  files: File[],
  projectId: number,
): Promise<InquiryResult> {
  const formData = new FormData();
  files.forEach((file) => formData.append("files", file));

  const query = new URLSearchParams();
  query.set("project_id", String(projectId));

  const suffix = query.size ? `?${query.toString()}` : "";
  const response = await fetch(`${API_BASE_URL}/inquiry/parse${suffix}`, {
    method: "POST",
    body: formData,
  });
  await ensureOk(response);
  return (await response.json()) as InquiryResult;
}

export async function listProjects(): Promise<ProjectSummary[]> {
  const response = await fetch(`${API_BASE_URL}/projects`);
  await ensureOk(response);
  return (await response.json()) as ProjectSummary[];
}

export async function createProject(payload: {
  name: string;
  description?: string;
}): Promise<ProjectSummary> {
  const response = await fetch(`${API_BASE_URL}/projects`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  await ensureOk(response);
  return (await response.json()) as ProjectSummary;
}

export async function createInquiryJob(
  files: File[],
  projectId: number,
): Promise<InquiryJobSnapshot> {
  const formData = new FormData();
  files.forEach((file) => formData.append("files", file));

  const response = await fetch(
    `${API_BASE_URL}/inquiry/jobs?project_id=${encodeURIComponent(String(projectId))}`,
    {
      method: "POST",
      body: formData,
    },
  );
  await ensureOk(response);
  return (await response.json()) as InquiryJobSnapshot;
}

export async function getInquiryJob(jobId: string): Promise<InquiryJobSnapshot> {
  const response = await fetch(`${API_BASE_URL}/inquiry/jobs/${encodeURIComponent(jobId)}`);
  await ensureOk(response);
  return (await response.json()) as InquiryJobSnapshot;
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
