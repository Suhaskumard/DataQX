const API_BASE_URL = "http://localhost:8000";

async function parseOrThrow(response: Response): Promise<any> {
  const body = await response.json().catch(() => null);
  if (!response.ok) {
    const detail = body?.detail || `Request failed with status ${response.status}`;
    throw new Error(detail);
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

export function getPowerBiReadiness(runId: string): Promise<any> {
  return getJson(`/api/powerbi/${runId}`);
}

export function getDrift(runId: string): Promise<any> {
  return getJson(`/api/drift/${runId}`);
}

export function reportUrl(runId: string): string {
  return `${API_BASE_URL}/api/report/${runId}`;
}
