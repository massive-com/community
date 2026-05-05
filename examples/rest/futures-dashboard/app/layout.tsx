import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Massive Futures Dashboard",
  description:
    "Cross-asset futures dashboard built on Massive's REST API. Term structures, contract drilldowns, exchange status across CME, CBOT, NYMEX, and COMEX.",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
