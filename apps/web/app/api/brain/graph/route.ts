import { NextRequest, NextResponse } from "next/server";
import { proxyJson } from "../../_backend";

export async function GET(request: NextRequest) {
  const search = request.nextUrl.search || "";
  const proxied = await proxyJson(`/api/brain/graph${search}`);
  return NextResponse.json(
    proxied?.body ?? {
      view: request.nextUrl.searchParams.get("view") ?? "local",
      nodes: [],
      edges: [],
      layers_missing: [{ layer: "brain_graph", reason: "local_backend_unavailable" }],
      honesty: { missing_layers_are_reported: true },
    },
    { status: proxied?.status ?? 503 },
  );
}
