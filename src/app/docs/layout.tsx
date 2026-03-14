import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Clark MCP — Integration docs | Krypton",
  description:
    "How to integrate and use the Krypton Strands HTTP MCP server (Clark MCP) with Cursor or other MCP clients.",
};

export default function DocsLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return <>{children}</>;
}
