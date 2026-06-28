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

  // Fail fast per-candidate: a backend whose port is open but unresponsive (e.g.
  // wedged mid hot-reload) would otherwise hang the request forever and never let
  // us fail over to a healthy companion or the static fallback. Abort after a
  // short budget so the next candidate / fallback is reached promptly.
  const PER_TRY_MS = Number(process.env.ATANOR_PROXY_TIMEOUT_MS ?? 3500);

  let lastError: unknown = null;
  for (const baseUrl of bases) {
    if (!baseUrl) continue;
    const ctrl = new AbortController();
    const timer = setTimeout(() => ctrl.abort(), PER_TRY_MS);
    try {
      const response = await fetch(`${baseUrl}${path}`, {
        ...init,
        cache: "no-store",
        signal: ctrl.signal,
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
    } finally {
      clearTimeout(timer);
    }
  }
  if (lastError) {
    throw lastError;
  }
  return null;
}
