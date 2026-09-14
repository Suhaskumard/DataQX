const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";

function formatErrorDetail(detail: unknown, status: number): string {
  if (typeof detail === "string" && detail) return detail;
  if (Array.isArray(detail) && detail.length > 0) {
    // FastAPI's default 422 validation-error shape is an array of
    // {loc, msg, type} objects, not a string -- without this, `new Error(detail)`
    // stringifies the array to the useless literal "[object Object]".
    return detail
      .map((item) => (item && typeof item === "object" && "msg" in item ? String((item as any).msg) : String(item)))
      .join("; ");
  }
  return `Request failed with status ${status}`;
}

async function parseOrThrow(response: Response): Promise<any> {
  const body = await response.json().catch(() => null);
  if (!response.ok) {
    throw new Error(formatErrorDetail(body?.detail, response.status));
  }
  return body;
}

export async function uploadDataset(files: File[], projectPlanText?: string): Promise<any> {
  const formData = new FormData();
  for (const file of files) {
    formData.append("files", file);
  }
  if (projectPlanText) {
    formData.append("project_plan_text", projectPlanText);
  }

  const response = await fetch(`${API_BASE_URL}/api/upload`, {
    method: "POST",
    body: formData,
  });
  return parseOrThrow(response);
}

async function postRunAction(path: string, runId: string): Promise<any> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ run_id: runId }),
  });
  return parseOrThrow(response);
}

export function analyzeRun(runId: string): Promise<any> {
  return postRunAction("/api/analyze", runId);
}

export function cleanRun(runId: string): Promise<any> {
  return postRunAction("/api/clean", runId);
}

export function validateRun(runId: string): Promise<any> {
  return postRunAction("/api/validate", runId);
}

async function getJson(path: string): Promise<any> {
  const response = await fetch(`${API_BASE_URL}${path}`);
  return parseOrThrow(response);
}

export function getIssues(runId: string): Promise<any> {
  return getJson(`/api/issues/${runId}`);
}

export function getQuality(runId: string): Promise<any> {
  return getJson(`/api/quality/${runId}`);
}

export function getAnalyticsReadiness(runId: string): Promise<any> {
  return getJson(`/api/analytics-readiness/${runId}`);
}

export function getDrift(runId: string): Promise<any> {
  return getJson(`/api/drift/${runId}`);
}

export function getLineage(runId: string): Promise<any> {
  return getJson(`/api/lineage/${runId}`);
}

export function getAudit(runId: string): Promise<any> {
  return getJson(`/api/audit/${runId}`);
}

export function getBeforeAfter(runId: string): Promise<any> {
  return getJson(`/api/before-after/${runId}`);
}

export function getDictionary(runId: string): Promise<any> {
  return getJson(`/api/dictionary/${runId}`);
}

export function getPerformance(runId: string): Promise<any> {
  return getJson(`/api/performance/${runId}`);
}

export function reportUrl(runId: string): string {
  return `${API_BASE_URL}/api/report/${runId}`;
}

export function downloadUrl(runId: string, filename: string): string {
  return `${API_BASE_URL}/api/download/${runId}/${encodeURIComponent(filename)}`;
}
