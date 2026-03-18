import { readFile } from "fs/promises";
import path from "path";
import Link from "next/link";
import { extractHeadings, markdownToHtml } from "@/lib/markdown";

const DOC_PATH = path.join(process.cwd(), "public", "docs", "clark-mcp.md");

export default async function DocsPage() {
  let markdown = "";
  try {
    markdown = await readFile(DOC_PATH, "utf8");
  } catch {
    markdown = "# Docs not found\n\nMissing `public/docs/clark-mcp.md`.";
  }

  const headings = extractHeadings(markdown);
  const html = markdownToHtml(markdown);

  return (
    <div className="min-h-screen w-full bg-[#001C1B] text-white">
      <header className="sticky top-0 z-50 backdrop-blur-md bg-[#001C1B]/95 border-b border-white/10">
        <div className="max-w-6xl mx-auto px-4 sm:px-6 py-4 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <span className="text-[10px] uppercase tracking-[0.2em] text-white/50">
              Krypton
            </span>
            <span className="text-white/15">/</span>
            <span className="text-[10px] uppercase tracking-[0.2em] text-white/60">
              Docs
            </span>
          </div>
          <Link
            href="/clark"
            className="text-xs text-white/70 hover:text-white transition-colors"
          >
            Back to Clark
          </Link>
        </div>
      </header>

      <main className="max-w-6xl mx-auto px-4 sm:px-6 py-10 pb-20">
        <div className="grid grid-cols-1 lg:grid-cols-[240px_minmax(0,1fr)] gap-10">
          <aside className="hidden lg:block">
            <div className="sticky top-20">
              <div className="text-[11px] uppercase tracking-[0.18em] text-white/50 mb-3">
                On this page
              </div>
              <nav className="space-y-1">
                {headings.length === 0 ? (
                  <div className="text-sm text-white/50">No sections</div>
                ) : (
                  headings.map((h) => (
                    <a
                      key={`${h.depth}-${h.id}`}
                      href={`#${h.id}`}
                      className={[
                        "block text-sm hover:text-white transition-colors",
                        h.depth === 2
                          ? "text-white/75"
                          : "text-white/55 pl-3",
                      ].join(" ")}
                    >
                      {h.text}
                    </a>
                  ))
                )}
              </nav>
            </div>
          </aside>

          <article className="min-w-0">
            <div
              className="space-y-4"
              dangerouslySetInnerHTML={{ __html: html }}
            />

            <div className="pt-10 mt-10 border-t border-white/10">
              <div className="text-xs text-white/60">
                Edit the source in{" "}
                <code className="px-1.5 py-0.5 rounded bg-white/10 font-mono">
                  public/docs/clark-mcp.md
                </code>
                .
              </div>
            </div>
          </article>
        </div>
      </main>
    </div>
  );
}
