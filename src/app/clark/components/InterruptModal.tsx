"use client"

import React from 'react'
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription } from '@/components/ui/dialog'
import { Button } from '@/components/ui/button'

interface Interrupt {
  id: string
  name: string
  reason: {
    // krypton-pay-approval
    receiver_username?: string
    to_token?: string
    received_amount?: number
    from_token?: string
    operation?: string
    // krypton-fund-order-approval
    symbol?: string
    side?: 'buy' | 'sell'
    qty?: number
    strategy_id?: string | null
    order_id?: string
    impact_preview?: {
      quote_price?: number
      notional_usd?: number
      nav_before?: number
      cash_before?: number
      cash_after?: number
    }
  }
}

interface InterruptModalProps {
  isOpen: boolean
  interrupts: Interrupt[]
  onApprove: (interruptId: string) => void
  onReject: (interruptId: string) => void
}

const money = (n?: number) =>
  n == null ? '—' : `$${Number(n).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`

export default function InterruptModal({ isOpen, interrupts, onApprove, onReject }: InterruptModalProps) {
  if (!interrupts || interrupts.length === 0) return null

  const active = interrupts.find(
    (i) => i.name === 'krypton-pay-approval' || i.name === 'krypton-fund-order-approval',
  )
  if (!active) return null

  const isOrder = active.name === 'krypton-fund-order-approval'
  const { reason } = active

  const shell = (
    title: string,
    description: string,
    body: React.ReactNode,
    confirmLabel: string,
  ) => (
    <Dialog open={isOpen} onOpenChange={() => {}}>
      <DialogContent className="sm:max-w-md bg-[var(--kt-surface)] backdrop-blur-xl border border-[var(--kt-border)] rounded-2xl shadow-2xl">
        <DialogHeader>
          <DialogTitle className="text-xl font-semibold text-[var(--kt-accent-soft)]">{title}</DialogTitle>
          <DialogDescription className="text-[var(--kt-accent)]/80 mt-2">{description}</DialogDescription>
        </DialogHeader>
        <div className="mt-4 space-y-4">
          <div className="bg-[var(--kt-inset)]/30 rounded-lg p-4 border border-teal-700/30">
            <div className="space-y-3">{body}</div>
          </div>
          <div className="flex gap-3 pt-2">
            <Button
              onClick={() => onReject(active.id)}
              variant="outline"
              className="flex-1 bg-[var(--kt-down)]/10 hover:bg-[var(--kt-down)]/10 border-red-700/50 text-[var(--kt-down)] hover:text-red-100"
            >
              {isOrder ? 'Decline' : 'Cancel'}
            </Button>
            <Button onClick={() => onApprove(active.id)} className="flex-1 bg-teal-600 hover:bg-teal-700 text-[var(--kt-text-strong)]">
              {confirmLabel}
            </Button>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  )

  const Row = ({ label, value, strong }: { label: string; value: React.ReactNode; strong?: boolean }) => (
    <div className="flex justify-between items-center">
      <span className="text-[var(--kt-accent-soft)]/80">{label}:</span>
      <span className={`text-[var(--kt-text)] ${strong ? 'font-semibold' : 'font-medium'}`}>{value}</span>
    </div>
  )

  if (isOrder) {
    const p = reason.impact_preview || {}
    const side = (reason.side || 'buy').toUpperCase()
    return shell(
      'Confirm Trade',
      'Review this order before it executes.',
      <>
        <Row
          label="Order"
          value={
            <span className={reason.side === 'sell' ? 'text-[var(--kt-down)]' : 'text-[var(--kt-up)]'}>
              {side} {reason.qty} {reason.symbol}
            </span>
          }
          strong
        />
        {reason.strategy_id ? <Row label="Strategy" value={reason.strategy_id} /> : null}
        {p.quote_price != null ? <Row label="Price" value={money(p.quote_price)} /> : null}
        {p.notional_usd != null ? <Row label="Notional" value={money(p.notional_usd)} strong /> : null}
        {p.cash_before != null && p.cash_after != null ? (
          <Row label="Cash" value={`${money(p.cash_before)} → ${money(p.cash_after)}`} />
        ) : null}
      </>,
      'Approve',
    )
  }

  // krypton-pay-approval (unchanged behaviour)
  const operation = reason.operation === 'swap_and_transfer' ? 'Swap & Transfer' : 'Transfer'
  const toToken = reason.to_token || ''
  return shell(
    'Confirm Payment',
    'Please review and confirm the payment details below.',
    <>
      {reason.operation === 'swap_and_transfer' && reason.from_token ? (
        <Row label="Swap From" value={reason.from_token} />
      ) : null}
      <Row label="Send Amount" value={`${reason.received_amount} ${toToken}`} strong />
      <Row label="To" value={`@${reason.receiver_username}`} />
      <Row label="Operation" value={operation} />
    </>,
    'Confirm',
  )
}
