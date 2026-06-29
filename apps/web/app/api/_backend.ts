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

// The shared Cloud Brain runs always-on in the cloud (Oracle VM, HTTPS). The
// exe / web app fetches the Cloud Brain tab live from there, while Local Brain
// and chat stay on the local companion. Set CLOUD_BRAIN_BASE (baked into the exe
// build) to route only `/api/cloud-brain/*` to the cloud endpoint.
export function cloudBrainBase(): string | null {
  return process.env.CLOUD_BRAIN_BASE || process.env.NEXT_PUBLIC_CLOUD_BRAIN_BASE || null;
}

export async function proxyJson(path: string, init?: RequestInit) {
  // Cloud-Brain calls prefer the always-on cloud endpoint (when configured),
  // then fall back to local companions for resilience. Everything else stays local.
  const cloud = cloudBrainBase();
  const bases =
    cloud && path.startsWith("/api/cloud-brain/")
      ? [cloud, ...backendBaseCandidates()]
      : backendBaseCandidates();

  // Per-candidate budget. This must accommodate the SLOWEST legitimate endpoint —
  // /api/chat/atanor does graph routing + holographic fold + realization (~3-7s, and
  // up to ~30s+ with live web search). The previous 3.5s budget aborted every chat
  // request ("fetch failed" -> 502) while fast status endpoints (<0.1s) were unaffected,
  // which read as "응답없음". A wedged backend now takes longer to fail over, but the
  // client carries its own timeout and the alternate companions are usually absent.
  const PER_TRY_MS = Number(process.env.ATANOR_PROXY_TIMEOUT_MS ?? 45000);

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
