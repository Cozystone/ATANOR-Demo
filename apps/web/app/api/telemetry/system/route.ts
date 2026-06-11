import { NextResponse } from "next/server";
import { proxyJson } from "../../_backend";

export async function GET() {
  try {
    const proxied = await proxyJson("/api/telemetry/system");
    if (proxied) return NextResponse.json(proxied.body, { status: proxied.status });
    return NextResponse.json({ cpu_count: 2, disk_total_gb: 1, disk_used_gb: 0.1, timestamp: new Date().toISOString() });
  } catch {
    return NextResponse.json({ cpu_count: 2, disk_total_gb: 1, disk_used_gb: 0.1, timestamp: new Date().toISOString() });
  }
}
