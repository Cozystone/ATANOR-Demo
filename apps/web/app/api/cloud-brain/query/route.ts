import { NextResponse } from "next/server";
import { demoCloudBrainQuery } from "../../_alphaDemo";
import { proxyJson } from "../../_backend";

export async function POST(request: Request) {
  const body = await request.text();
  let query = "GraphRAG memory";
  try {
    query = JSON.parse(body || "{}").query ?? query;
  } catch {
    // Use default query.
  }
  try {
    const proxied = await proxyJson("/api/cloud-brain/query", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body,
    });
    if (proxied) return NextResponse.json(proxied.body, { status: proxied.status });
    return NextResponse.json(demoCloudBrainQuery(query));
  } catch {
    return NextResponse.json(demoCloudBrainQuery(query));
  }
}
