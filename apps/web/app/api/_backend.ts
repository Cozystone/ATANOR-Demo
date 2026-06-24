export function backendBaseUrl() {
  return backendBaseCandidates()[0] ?? "";
}

export function backendBaseCandidates() {
  const explicit = [
    process.env.ATANOR_GATEWAY_API,
    process.env.HOMAGE_GATEWAY_API,
    process.env.API_BASE_URL,
  ].filter((value): value is string => Boolean(value));
  if (process.env.VERCEL) return explicit;
  return Array.from(new Set([
    ...explicit,
    // Prefer the live companion that carries the product conversation +
    // SPLATRA scene contracts. Older healthy companions may answer /health
    // while lacking the current hologram scene payload.
    "http://127.0.0.1:8502",
    "http://127.0.0.1:8504",
    "http://127.0.0.1:8500",
  ]));
}

export async function proxyJson(path: string, init?: RequestInit) {
  const bases = backendBaseCandidates();

  let lastError: unknown = null;
  for (const baseUrl of bases) {
    if (!baseUrl) continue;
    try {
      const response = await fetch(`${baseUrl}${path}`, {
        ...init,
        cache: "no-store",
      });
      if (response.status === 404 || response.status === 405) {
        continue;
      }
      return {
        body: await response.json(),
        status: response.status,
      };
    } catch (error) {
      lastError = error;
    }
  }
  if (lastError) {
    throw lastError;
  }
  return null;
}
