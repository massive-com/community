import { NextResponse } from "next/server";
import { getMarketStatus, getExchanges } from "@/lib/massive";
import type { VenueStatus } from "@/lib/types";

export const dynamic = "force-dynamic";
export const revalidate = 30;

const MAJOR_VENUES = ["XCME", "XCBT", "XNYM", "XCEC"];

function centralTimeParts(date: Date): { weekday: string; hour: number } {
  const parts = new Intl.DateTimeFormat("en-US", {
    timeZone: "America/Chicago",
    weekday: "short",
    hour: "numeric",
    hourCycle: "h23",
  }).formatToParts(date);
  return {
    weekday: parts.find((p) => p.type === "weekday")?.value ?? "",
    hour: Number(parts.find((p) => p.type === "hour")?.value ?? -1),
  };
}

function isMaintenanceWindow(date: Date): boolean {
  const { weekday, hour } = centralTimeParts(date);
  return weekday !== "Sat" && weekday !== "Sun" && hour === 16;
}

export async function GET() {
  try {
    const [statuses, exchanges] = await Promise.all([
      getMarketStatus({ limit: 1000 }),
      getExchanges({ limit: 100 }),
    ]);

    const venueAcc: Record<
      string,
      { open: number; paused: number; closed: number; total: number }
    > = {};
    for (const s of statuses) {
      const v = s.trading_venue;
      if (!v) continue;
      venueAcc[v] = venueAcc[v] ?? { open: 0, paused: 0, closed: 0, total: 0 };
      venueAcc[v].total += 1;
      if (s.market_event === "open") venueAcc[v].open += 1;
      else if (s.market_event === "pause") venueAcc[v].paused += 1;
      else if (s.market_event === "close") venueAcc[v].closed += 1;
    }

    const maintenance = isMaintenanceWindow(new Date());
    const venueStatus: VenueStatus[] = MAJOR_VENUES.map((mic) => {
      const ex = exchanges.find((e) => e.mic === mic);
      const acc = venueAcc[mic] ?? { open: 0, paused: 0, closed: 0, total: 0 };
      const state =
        acc.total > 0 && acc.open / acc.total > 0.25
          ? "open"
          : acc.paused > 0
            ? "paused"
            : maintenance
              ? "maintenance"
              : "closed";
      const label =
        state === "open"
          ? "open"
          : state === "paused"
            ? "paused"
            : state === "maintenance"
              ? "maintenance"
              : "closed";
      return {
        mic,
        acronym: ex?.acronym ?? mic,
        name: ex?.name ?? mic,
        open: acc.open,
        total: acc.total,
        is_open: state === "open",
        state,
        label,
      };
    });

    return NextResponse.json({
      venues: venueStatus,
      asof: new Date().toISOString(),
    });
  } catch (err: unknown) {
    return NextResponse.json(
      { error: err instanceof Error ? err.message : "overview_failed" },
      { status: 500 }
    );
  }
}
