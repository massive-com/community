import { NextResponse } from "next/server";

// Derive the WebSocket base URL from MASSIVE_WS_BASE (explicit) or fall back to
// inferring it from MASSIVE_API_BASE (e.g. https://api.staging.massive.com ->
// wss://socket.staging.massive.com).
function resolveWsBase(): string {
  const explicit = process.env.MASSIVE_WS_BASE?.trim();
  if (explicit) return explicit.replace(/\/+$/, "");

  const apiBase = process.env.MASSIVE_API_BASE?.trim();
  if (apiBase) {
    // https://api.staging.massive.com -> wss://socket.staging.massive.com
    const wsBase = apiBase
      .replace(/^https?:\/\//, "wss://")
      .replace(/\/+$/, "")
      .replace(/\/\/api\./, "//socket.");
    return wsBase;
  }

  return "wss://socket.massive.com";
}

export async function GET() {
  const key = process.env.MASSIVE_API_KEY?.trim();
  if (!key) {
    return NextResponse.json({ error: "MASSIVE_API_KEY not configured" }, { status: 500 });
  }
  return NextResponse.json({ key, wsBase: resolveWsBase() });
}
