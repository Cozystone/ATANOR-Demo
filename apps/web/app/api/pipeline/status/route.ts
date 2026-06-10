import { NextResponse } from "next/server";

const apiBaseUrl = process.env.API_BASE_URL ?? "http://127.0.0.1:8000";

export async function GET() {
  try {
    const response = await fetch(`${apiBaseUrl}/api/pipeline/status`, {
      cache: "no-store",
    });

    if (!response.ok) {
      return NextResponse.json(
        { error: `Backend returned ${response.status}` },
        { status: 502 },
      );
    }

    return NextResponse.json(await response.json());
  } catch (error) {
    return NextResponse.json(
      {
        error:
          error instanceof Error
            ? error.message
            : "Unable to reach pipeline status backend",
      },
      { status: 502 },
    );
  }
}
