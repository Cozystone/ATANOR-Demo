import { NextResponse } from "next/server";

const apiBaseUrl = process.env.API_BASE_URL ?? "http://127.0.0.1:8000";

export async function POST(request: Request) {
  try {
    const body = await request.text();
    const response = await fetch(`${apiBaseUrl}/api/datagate/run`, {
      method: "POST",
      headers: body ? { "Content-Type": "application/json" } : undefined,
      body: body || undefined,
      cache: "no-store",
    });

    return NextResponse.json(await response.json(), { status: response.status });
  } catch (error) {
    return NextResponse.json(
      {
        error:
          error instanceof Error
            ? error.message
            : "Unable to start DataGate backend run",
      },
      { status: 502 },
    );
  }
}
