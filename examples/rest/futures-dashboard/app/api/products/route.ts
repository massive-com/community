import { NextResponse } from "next/server";
import { listProducts } from "@/lib/massive";
import { CURATED_FLAT } from "@/lib/curated-products";
import { todayISO } from "@/lib/format";

export const dynamic = "force-dynamic";
export const revalidate = 300;

const demoRank = new Map<string, number>();
for (const [i, p] of CURATED_FLAT.entries()) {
  demoRank.set(p.code, i);
  for (const v of p.variants ?? []) {
    demoRank.set(v.code, i + 0.1);
  }
}

const COMPLEX_PRODUCT_TERMS = [
  "average price",
  "balmo",
  "calendar spread",
  "crack spread",
  "daily spread",
  "freight",
  "housing",
  "seasonal strip",
  "strip",
  "tas",
  "weather",
];

function catalogRank(p: { product_code?: string; name?: string }): number {
  const ranked = p.product_code ? demoRank.get(p.product_code) : undefined;
  if (ranked !== undefined) return ranked;

  const name = (p.name ?? "").toLowerCase();
  if (COMPLEX_PRODUCT_TERMS.some((term) => name.includes(term))) return 50_000;
  return 10_000;
}

export async function GET() {
  try {
    const all = await listProducts({
      date: todayISO(),
      type: "single",
      limit: 5000,
    });

    const byCode = new Map<string, (typeof all)[number]>();
    for (const p of all) {
      if (p.product_code && !byCode.has(p.product_code)) {
        byCode.set(p.product_code, p);
      }
    }
    const unique = Array.from(byCode.values()).filter((p) => p.name);

    const groups: Record<
      string,
      { count: number; products: typeof unique }
    > = {};
    for (const p of unique) {
      const key =
        (p.asset_class ?? "other") + " · " + (p.asset_sub_class ?? "N/A");
      groups[key] = groups[key] ?? { count: 0, products: [] };
      groups[key].count += 1;
      groups[key].products.push(p);
    }

    const sectorGroups = Object.entries(groups)
      .map(([label, g]) => ({
        label,
        count: g.count,
        products: g.products
          .sort(
            (a, b) =>
              catalogRank(a) - catalogRank(b) ||
              (a.name ?? "").localeCompare(b.name ?? "")
          ),
      }))
      .sort((a, b) => b.count - a.count);

    return NextResponse.json({
      total: unique.length,
      groups: sectorGroups,
    });
  } catch (err: unknown) {
    return NextResponse.json(
      { error: err instanceof Error ? err.message : "products_failed" },
      { status: 500 }
    );
  }
}
