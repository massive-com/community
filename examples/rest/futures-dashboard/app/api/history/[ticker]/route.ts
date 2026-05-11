import { NextResponse } from "next/server";
import { getAggregates } from "@/lib/massive";

export const dynamic = "force-dynamic";

export async function GET(
  _req: Request,
  { params }: { params: Promise<{ ticker: string }> }
) {
  try {
    const { ticker } = await params;
    const t = ticker.toUpperCase();

    const ninetyDaysAgo = new Date();
    ninetyDaysAgo.setDate(ninetyDaysAgo.getDate() - 90);
    const histStart = ninetyDaysAgo.toISOString().slice(0, 10);

    const bars = await getAggregates({
      ticker: t,
      resolution: "1day",
      windowStartGte: histStart,
      limit: 90,
      sort: "window_start.asc",
    }).catch(() => []);

    return NextResponse.json({
      history: bars.map((b) => ({
        date: b.session_end_date ?? "",
        close: b.close,
        volume: b.volume,
      })),
    });
  } catch (err: unknown) {
    return NextResponse.json(
      { error: err instanceof Error ? err.message : "history_failed" },
      { status: 500 }
    );
  }
}
