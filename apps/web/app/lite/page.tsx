"use client";

import DemoApp from "../DemoApp";

// Local dev convenience: one dev server, two links.
//   /        → full New ATANOR (orb / particles / 3D)
//   /lite    → the lean GPT-style chat demo (this route)
// For a public deploy, set NEXT_PUBLIC_ATANOR_PROFILE=demo so `/` is the demo.
export default function LiteRoute() {
  return <DemoApp />;
}
