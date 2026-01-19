"use client"

import React from 'react'
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription } from '@/components/ui/dialog'
import { Button } from '@/components/ui/button'

interface Interrupt {
  id: string
  name: string
  reason: {
    receiver_username?: string
    to_token?: string
    received_amount?: number
    from_token?: string
    operation?: string
  }
}

interface InterruptModalProps {
  isOpen: boolean
  interrupts: Interrupt[]
  onApprove: (interruptId: string) => void
  onReject: (interruptId: string) => void
}

export default function InterruptModal({
  isOpen,
  interrupts,
  onApprove,
  onReject,
}: InterruptModalProps) {
  if (!interrupts || interrupts.length === 0) {
    return null
  }

  // Find the krypton-pay-approval interrupt
  const paymentInterrupt = interrupts.find((i) => i.name === 'krypton-pay-approval')

  if (!paymentInterrupt) {
    return null
  }

  const { reason } = paymentInterrupt
  const operation = reason.operation === 'swap_and_transfer' ? 'Swap & Transfer' : 'Transfer'
  const fromToken = reason.from_token || reason.to_token
  const toToken = reason.to_token || ''

  return (
    <Dialog open={isOpen} onOpenChange={() => {}}>
      <DialogContent className="sm:max-w-md bg-gradient-to-b from-[#1c2f2f]/95 to-[#0b1515]/95 backdrop-blur-xl border border-teal-700/50 rounded-2xl shadow-[0_20px_60px_rgba(0,0,0,0.8)]">
        <DialogHeader>
          <DialogTitle className="text-xl font-semibold text-teal-200">
            Confirm Payment
          </DialogTitle>
          <DialogDescription className="text-teal-300/80 mt-2">
            Please review and confirm the payment details below.
          </DialogDescription>
        </DialogHeader>

        <div className="mt-4 space-y-4">
          {/* Payment Details */}
          <div className="bg-teal-900/30 rounded-lg p-4 border border-teal-700/30">
            <div className="space-y-3">
              {reason.operation === 'swap_and_transfer' && reason.from_token && (
                <div className="flex justify-between items-center">
                  <span className="text-teal-200/80">Swap From:</span>
                  <span className="text-teal-100 font-medium">
                    {reason.from_token}
                  </span>
                </div>
              )}
              <div className="flex justify-between items-center">
                <span className="text-teal-200/80">Send Amount:</span>
                <span className="text-teal-100 font-semibold">
                  {reason.received_amount} {toToken}
                </span>
              </div>
              <div className="flex justify-between items-center">
                <span className="text-teal-200/80">To:</span>
                <span className="text-teal-100 font-medium">
                  @{reason.receiver_username}
                </span>
              </div>
              <div className="flex justify-between items-center">
                <span className="text-teal-200/80">Operation:</span>
                <span className="text-teal-100 font-medium">{operation}</span>
              </div>
            </div>
          </div>

          {/* Action Buttons */}
          <div className="flex gap-3 pt-2">
            <Button
              onClick={() => onReject(paymentInterrupt.id)}
              variant="outline"
              className="flex-1 bg-red-900/20 hover:bg-red-900/40 border-red-700/50 text-red-200 hover:text-red-100"
            >
              Cancel
            </Button>
            <Button
              onClick={() => onApprove(paymentInterrupt.id)}
              className="flex-1 bg-teal-600 hover:bg-teal-700 text-white"
            >
              Confirm
            </Button>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  )
}
