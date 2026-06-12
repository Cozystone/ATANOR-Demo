import { NextResponse } from "next/server";
import { demoGraphRAGQuery, isConversationalQuery, isLegendQuery, isNodeInventoryQuery } from "../../_alphaDemo";
import { proxyJson } from "../../_backend";
import { isFreshSearchQuery, isKnowledgeLookupQuery, searchWeb, webResultsToEvidence } from "../../_webSearch";

function isRawNoNodeResult(body: any) {
  const result = body?.result ?? {};
  const answer = String(result.answer ?? "");
  return (
    answer.includes("raw_no_node::")
    || result.method === "homage-native-raw-no-node-v1"
    || result.answer_engine?.mode === "native-raw-no-node-alpha"
  );
}

function isLegacySurfaceResult(body: any) {
  const result = body?.result ?? {};
  return (
    result.method === "homage-native-web-search-rag-v1"
    || result.method === "homage-native-graphrag-utterance-v1"
    || result.method === "homage-native-no-node-utterance-v1"
    || result.answer_engine?.mode === "native-web-search-grounded-alpha"
    || result.answer_engine?.mode === "native-next-thought-alpha"
    || result.answer_engine?.mode === "native-no-node-sentence-alpha"
  );
}

export async function POST(request: Request) {
  const body = await request.text();
  let query = "GraphRAG evidence";
  let webSearch = false;
  let webSearchProvider: string | null = null;
  try {
    const parsed = JSON.parse(body || "{}");
    query = parsed.query ?? query;
    webSearch = Boolean(parsed.web_search ?? false);
    webSearchProvider = parsed.web_search_provider ?? null;
  } catch {
    // Fall through to deterministic demo with the default query.
  }
  webSearch = webSearch || isFreshSearchQuery(query) || isKnowledgeLookupQuery(query);

  if (isConversationalQuery(query) || isLegendQuery(query) || isNodeInventoryQuery(query)) {
    return NextResponse.json(demoGraphRAGQuery(query));
  }

  try {
    const proxied = await proxyJson("/api/graphrag/query", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body,
    });
    if (proxied?.body?.result?.answer && !isRawNoNodeResult(proxied.body) && !isLegacySurfaceResult(proxied.body) && (!webSearch || proxied.body.result.web_search)) {
      return NextResponse.json(proxied.body, { status: proxied.status });
    }
  } catch {
    // Fall through to deterministic demo.
  }
  if (webSearch) {
    const webSearchPayload = await searchWeb(query, 5, webSearchProvider);
    return NextResponse.json(demoGraphRAGQuery(query, webResultsToEvidence(webSearchPayload.results), webSearchPayload));
  }
  return NextResponse.json(demoGraphRAGQuery(query));
}
