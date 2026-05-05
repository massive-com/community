import { NextResponse } from "next/server";
import { getUsageStats, resetUsageStats } from "@/lib/massive";

export const dynamic = "force-dynamic";

/**
 * GET  /api/_stats        → returns counters of upstream Massive API calls
 *                           grouped by SDK method since the last reset.
 * POST /api/_stats?reset=1 → zero out the counters.
 *
 * Counters live in process memory only; they are reset on server restart.
 */
export async function GET() {
  return NextResponse.json(getUsageStats());
}

export async function POST(req: Request) {
  const url = new URL(req.url);
  if (url.searchParams.get("reset") === "1") {
    resetUsageStats();
  }
  return NextResponse.json(getUsageStats());
}
