"use client"

/**
 * assistant-ui registrations for the shared tool-result panels.
 *
 * The panels themselves live in components/ToolResultPanels.tsx and are used
 * by BOTH surfaces — the classic chat renders them from message.toolResults,
 * this file just teaches assistant-ui's registry to use the same ones. A
 * backtest must look like the same backtest wherever it is read.
 */

import React from 'react'
import { makeAssistantToolUI } from '@assistant-ui/react'
import {
  BacktestPanel, BacktestToolResult,
  BarsPanel, BarsResult,
  IndicatorPanel, IndicatorResult,
  NavPanel, NavToolResult,
  ScreenPanel, ScreenResult,
} from '../components/ToolResultPanels'

export const MarketBarsUI = makeAssistantToolUI<Record<string, unknown>, BarsResult>({
  toolName: 'market_bars',
  render: ({ result, status }) =>
    status.type === 'running' || !result ? null : <BarsPanel result={result} />,
})

export const MarketIndicatorUI = makeAssistantToolUI<Record<string, unknown>, IndicatorResult>({
  toolName: 'market_indicator',
  render: ({ result, status }) =>
    status.type === 'running' || !result ? null : <IndicatorPanel result={result} />,
})

export const CryptoScreenUI = makeAssistantToolUI<Record<string, unknown>, ScreenResult>({
  toolName: 'crypto_screen',
  render: ({ result, status }) =>
    status.type === 'running' || !result ? null : <ScreenPanel result={result} />,
})

export const FundNavUI = makeAssistantToolUI<Record<string, unknown>, NavToolResult>({
  toolName: 'fund_nav',
  render: ({ result, status }) =>
    status.type === 'running' || !result ? null : <NavPanel result={result} />,
})

export const FundBacktestUI = makeAssistantToolUI<Record<string, unknown>, BacktestToolResult>({
  toolName: 'fund_backtest',
  render: ({ result, status }) =>
    status.type === 'running' || !result ? null : <BacktestPanel result={result} />,
})

/** Mount all tool UIs — rendering nothing itself, registering the renderers. */
export function ClarkToolUIs() {
  return (
    <>
      <MarketBarsUI />
      <MarketIndicatorUI />
      <CryptoScreenUI />
      <FundNavUI />
      <FundBacktestUI />
    </>
  )
}
