export function backendBaseUrl() {
  return process.env.API_BASE_URL ?? (process.env.VERCEL ? "" : "http://127.0.0.1:8000");
}

export async function proxyJson(path: string, init?: RequestInit) {
  const baseUrl = backendBaseUrl();
  if (!baseUrl) {
    return null;
  }

  const response = await fetch(`${baseUrl}${path}`, {
    ...init,
    cache: "no-store",
  });
  return {
    body: await response.json(),
    status: response.status,
  };
}
