import { NextResponse } from "next/server";
import { demoGraphRAGQuery } from "../../_alphaDemo";
import { proxyJson } from "../../_backend";

export async function POST(request: Request) {
  const body = await request.text();
  let query = "GraphRAG evidence";
  try {
    query = JSON.parse(body || "{}").query ?? query;
    const proxied = await proxyJson("/api/graphrag/query", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body,
    });
    if (proxied) return NextResponse.json(proxied.body, { status: proxied.status });
  } catch {
    // Fall through to deterministic demo.
  }
  return NextResponse.json(demoGraphRAGQuery(query));
}
