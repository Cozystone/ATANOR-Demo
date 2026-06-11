import { NextResponse } from "next/server";
import { demoGraphRAGQuery, isConversationalQuery, isLegendQuery, isNodeInventoryQuery } from "../../_alphaDemo";
import { proxyJson } from "../../_backend";

export async function POST(request: Request) {
  const body = await request.text();
  let query = "GraphRAG evidence";
  try {
    query = JSON.parse(body || "{}").query ?? query;
  } catch {
    // Fall through to deterministic demo with the default query.
  }

  if (isConversationalQuery(query) || isLegendQuery(query) || isNodeInventoryQuery(query)) {
    return NextResponse.json(demoGraphRAGQuery(query));
  }

  try {
    const proxied = await proxyJson("/api/graphrag/query", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body,
    });
    if (proxied?.body?.result?.answer) return NextResponse.json(proxied.body, { status: proxied.status });
  } catch {
    // Fall through to deterministic demo.
  }
  return NextResponse.json(demoGraphRAGQuery(query));
}
