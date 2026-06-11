import { NextResponse } from "next/server";

const apiBaseUrl = process.env.API_BASE_URL ?? "http://127.0.0.1:8000";

export async function GET() {
  try {
    const response = await fetch(`${apiBaseUrl}/api/datagate/status`, {
      cache: "no-store",
    });

    return NextResponse.json(await response.json(), { status: response.status });
  } catch (error) {
    return NextResponse.json(
      {
        error:
          error instanceof Error
            ? error.message
            : "Unable to reach DataGate backend status",
      },
      { status: 502 },
    );
  }
}
