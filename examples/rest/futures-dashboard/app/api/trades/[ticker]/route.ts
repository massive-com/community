import { NextResponse } from "next/server";
import { getTrades, getQuotes } from "@/lib/massive";

export const dynamic = "force-dynamic";

export async function GET(
  _req: Request,
  { params }: { params: Promise<{ ticker: string }> }
) {
  const { ticker } = await params;
  const t = ticker.toUpperCase();

  const [trades, quotes] = await Promise.all([
    getTrades({ ticker: t, limit: 30 }).catch(() => []),
    getQuotes({ ticker: t, limit: 50 }).catch(() => []),
  ]);

  return NextResponse.json({ recent_trades: trades, recent_quotes: quotes });
}
