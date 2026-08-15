"use client"

/**
 * /clark/next — the assistant-ui chat surface, running in parallel with the
 * main chat until it reaches parity (citations, terminal, devtools). Same
 * SSE, same design language; the new capability is generative tool UIs:
 * a fund_backtest answer arrives with its real equity curve, market_bars
 * with its real price chart — components rendered from the spine's own
 * numbers, never from prose.
 */

import React from 'react'
import Link from 'next/link'
import { ArrowUp } from 'lucide-react'
import {
  ComposerPrimitive,
  MessagePrimitive,
  ThreadPrimitive,
} from '@assistant-ui/react'
import { markdownToHtml } from '../utils/markdown'
import { ClarkRuntimeProvider } from './runtime'
import { ClarkToolUIs } from './toolUIs'

const UserMessage = () => (
  <MessagePrimitive.Root className="flex justify-end px-4 py-2">
    <div className="max-w-[80%] rounded-2xl border border-[var(--kt-border)] bg-[var(--kt-inset)] px-4 py-2 text-sm text-[var(--kt-text)]">
      <MessagePrimitive.Parts />
    </div>
  </MessagePrimitive.Root>
)

/** Markdown through the same renderer as the main chat, so figures get the
 *  measured register (mono clark-num) here too. */
const MarkdownText = ({ text }: { text: string }) => (
  <div
    className="clark-prose max-w-none text-sm leading-relaxed text-[var(--kt-text)]"
    dangerouslySetInnerHTML={{ __html: markdownToHtml(text) }}
  />
)

const AssistantMessage = () => (
  <MessagePrimitive.Root className="px-4 py-2">
    <div className="flex items-center gap-2">
      <img src="/clark process.svg" alt="" className="h-6 w-6 opacity-90" />
      <span className="text-xs font-medium text-[var(--kt-text)]">Clark</span>
    </div>
    <div className="ml-8 mt-1 max-w-[85%] border-l-2 border-[var(--kt-border)] pl-4">
      <MessagePrimitive.Parts
        components={{
          Text: ({ text }) => <MarkdownText text={text} />,
        }}
      />
    </div>
  </MessagePrimitive.Root>
)

export default function ClarkNextPage() {
  return (
    <ClarkRuntimeProvider>
      <ClarkToolUIs />
      <div className="flex h-screen flex-col bg-[var(--kt-bg)]" data-kt-theme="dark">
        <div className="flex items-center gap-3 border-b border-[var(--kt-border)] px-4 py-2.5">
          <img src="/Krypton Clark.svg" alt="" className="h-5 w-auto" />
          <span className="text-[13px] font-semibold text-[var(--kt-text-strong)]">
            Clark <span className="font-normal text-[var(--kt-text-muted)]">· next</span>
          </span>
          <span className="text-[11px] text-[var(--kt-text-muted)]">
            generative answers — every component is a tool result, not an invention
          </span>
          <Link href="/clark" className="ml-auto text-[11px] text-[var(--kt-accent)] hover:underline">
            classic chat →
          </Link>
        </div>

        <ThreadPrimitive.Root className="flex min-h-0 flex-1 flex-col">
          <ThreadPrimitive.Viewport className="min-h-0 flex-1 overflow-y-auto py-4">
            <ThreadPrimitive.Empty>
              <div className="flex h-full flex-col items-center justify-center gap-2 px-6 text-center">
                <div className="text-sm text-[var(--kt-text)]">
                  Ask about the fund — answers arrive with their receipts rendered.
                </div>
                <div className="text-[11px] text-[var(--kt-text-muted)]">
                  Try: &ldquo;What is the fund NAV right now?&rdquo; ·
                  &ldquo;RSI for AAPL&rdquo; · &ldquo;Backtest NVDA over 6 months with SMA&rdquo;
                </div>
              </div>
            </ThreadPrimitive.Empty>
            <ThreadPrimitive.Messages
              components={{ UserMessage, AssistantMessage }}
            />
          </ThreadPrimitive.Viewport>

          <div className="border-t border-[var(--kt-border)] p-3">
            <ComposerPrimitive.Root className="mx-auto flex max-w-[820px] items-end gap-2 rounded-xl border border-[var(--kt-border)] bg-[var(--kt-inset)] px-3 py-2">
              <ComposerPrimitive.Input
                rows={1}
                placeholder="Ask Clark about the fund…"
                className="max-h-40 flex-1 resize-none bg-transparent text-sm text-[var(--kt-text)] outline-none placeholder:text-[var(--kt-text-muted)]"
              />
              <ComposerPrimitive.Send className="rounded-lg border border-[var(--kt-accent-border)] bg-[var(--kt-accent-bg)] p-1.5 text-[var(--kt-accent)] transition-colors hover:border-[var(--kt-accent)] disabled:opacity-40">
                <ArrowUp size={14} />
              </ComposerPrimitive.Send>
            </ComposerPrimitive.Root>
            <div className="mx-auto mt-1.5 max-w-[820px] text-center text-[10px] text-[var(--kt-text-muted)]">
              Advises only — cannot place or approve an order. Proposals land in the approval queue.
            </div>
          </div>
        </ThreadPrimitive.Root>
      </div>
    </ClarkRuntimeProvider>
  )
}
