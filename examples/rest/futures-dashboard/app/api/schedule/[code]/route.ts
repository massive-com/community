import { NextResponse } from "next/server";
import { getSchedules } from "@/lib/massive";
import { todayISO } from "@/lib/format";

export const dynamic = "force-dynamic";

const SCHEDULE_TIMEOUT_MS = 6000;

export async function GET(
  _req: Request,
  { params }: { params: Promise<{ code: string }> }
) {
  try {
    const { code } = await params;
    const events = await Promise.race([
      getSchedules({
        productCode: code.toUpperCase(),
        sessionEndDateGte: todayISO(),
        limit: 12,
      }),
      new Promise<[]>((resolve) =>
        setTimeout(() => resolve([]), SCHEDULE_TIMEOUT_MS)
      ),
    ]);
    return NextResponse.json({ events });
  } catch (err: unknown) {
    return NextResponse.json({
      events: [],
      error: err instanceof Error ? err.message : "schedule_failed",
    });
  }
}
