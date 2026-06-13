export function backendBaseUrl() {
  return process.env.ATANOR_GATEWAY_API ?? process.env.HOMAGE_GATEWAY_API ?? process.env.API_BASE_URL ?? (process.env.VERCEL ? "" : "http://127.0.0.1:8500");
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
  if (response.status === 404 || response.status === 405) {
    return null;
  }
  return {
    body: await response.json(),
    status: response.status,
  };
}
