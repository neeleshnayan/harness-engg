import type { ChatMessage } from '../types'

/**
 * Strip any leading reasoning block (e.g. leaked {'reasoningContent': ...}) from
 * message text so only user-facing content is shown. Safe to call on any string.
 */
export function stripReasoningFromMessage(text: string): string {
  if (!text || typeof text !== 'string') return text
  if (!text.includes('reasoningContent') && !text.includes('reasoningText')) return text
  const lines = text.split('\n')
  for (let i = 0; i < lines.length; i++) {
    const line = lines[i]
    const trimmed = line.trim()
    if (!trimmed) continue
    if (trimmed.includes('reasoningContent') || trimmed.includes('reasoningText')) continue
    return lines.slice(i).join('\n').trim()
  }
  return text
}

/** Recursively find first non-empty string at key 'message' or 'markdown' (max depth 4). */
function deepMessageFrom(obj: unknown, depth = 0): string | undefined {
  if (depth > 4 || obj == null) return undefined
  if (typeof obj === 'string' && obj.trim().length > 0) return obj.trim()
  if (typeof obj !== 'object') return undefined
  const o = obj as Record<string, unknown>
  for (const k of ['message', 'markdown', 'text', 'content', 'output']) {
    const v = o[k]
    if (typeof v === 'string' && v.trim().length > 0) return v.trim()
    const nested = deepMessageFrom(v, depth + 1)
    if (nested) return nested
  }
  for (const v of Object.values(o)) {
    const nested = deepMessageFrom(v, depth + 1)
    if (nested) return nested
  }
  return undefined
}

function messageFromDataObject(d: Record<string, unknown>): string | undefined {
  if (!d || typeof d !== 'object') return undefined
  for (const v of Object.values(d)) {
    if (v && typeof v === 'object' && typeof (v as { message?: string }).message === 'string') {
      const msg = (v as { message: string }).message
      if (msg.trim()) return msg
    }
  }
  return undefined
}

/** Build a ChatMessage from the agents/query API payload. Shared by /clark page and MiniClarkChat. */
export function createAssistantMessage(payload: unknown): ChatMessage {
  const p = payload as Record<string, unknown> | null | undefined
  const messageId = (Date.now() + Math.random()).toString()

  const dataObj = p?.data as Record<string, unknown> | undefined
  const dataMarkdown = (dataObj?.markdown as string | undefined)
    ?? (dataObj?.economic as { markdown?: string } | undefined)?.markdown
  const dataMessage = typeof dataObj?.message === 'string' ? dataObj.message : undefined
  const agentMessage = dataObj && typeof dataObj === 'object' ? messageFromDataObject(dataObj) : undefined
  const deepFallback = p && (p as { success?: boolean }).success !== false ? deepMessageFrom(p) : undefined
  const fallbackText = "Sorry, I'm unable to process your request at the moment."

  let responseMessage: string =
    (typeof p?.message === 'string' && (p.message as string).trim() ? p.message : undefined) ??
    dataMarkdown ??
    dataMessage ??
    agentMessage ??
    deepFallback ??
    fallbackText

  responseMessage = stripReasoningFromMessage(responseMessage)

  const rawData = p?.data as Record<string, unknown> | undefined

  const regulationResult = rawData?.regulation_result ?? rawData?.regulationResult
  if (regulationResult) responseMessage = ''

  let backtestResult = rawData?.backtest_result ?? rawData?.backtestResult
  if (!backtestResult && rawData) {
    if (rawData.technical && typeof rawData.technical === 'object' && (rawData.technical as Record<string, unknown>).backtest_result)
      backtestResult = (rawData.technical as Record<string, unknown>).backtest_result
    else if (rawData.backtest && typeof rawData.backtest === 'object' && (rawData.backtest as Record<string, unknown>).backtest_result)
      backtestResult = (rawData.backtest as Record<string, unknown>).backtest_result
    else if (rawData.data_fetcher && (rawData.backtest_result || (rawData.backtest as Record<string, unknown>)?.backtest_result))
      backtestResult = rawData.backtest_result ?? (rawData.backtest as Record<string, unknown>)?.backtest_result
  }

  const priceHistoryData = rawData?.price_history ?? rawData?.priceHistory
  let dataPoints = (priceHistoryData as Record<string, unknown> | undefined)?.data_points ?? (priceHistoryData as Record<string, unknown> | undefined)?.data
  if (!dataPoints && Array.isArray(priceHistoryData)) dataPoints = priceHistoryData
  const hasValidPricePoints = Array.isArray(dataPoints) && dataPoints.length > 0 &&
    (dataPoints as { price?: number }[]).some((pt) => typeof pt?.price === 'number')
  const rawToken = (rawData?.token ?? (priceHistoryData as Record<string, unknown>)?.token ?? (p?.parsed_intent as Record<string, unknown>)?.token_name ?? '') as string
  const displayTokenForHistory = (rawToken || '').replace(/^k/i, '') || rawToken
  const priceHistoryResult = priceHistoryData && hasValidPricePoints && Array.isArray(dataPoints)
    ? {
        token: displayTokenForHistory,
        lookback_days: ((priceHistoryData as Record<string, unknown>)?.lookback_days ?? (p?.parsed_intent as Record<string, unknown>)?.lookback_days ?? 30) as number,
        count: ((priceHistoryData as Record<string, unknown>)?.count ?? (dataPoints as unknown[]).length ?? 0) as number,
        data_points: dataPoints,
      }
    : undefined

  const balanceSource = rawData?.balances != null || rawData?.dailyBalances != null || rawData?.intradayBalances != null
    ? rawData
    : (rawData?.krypton_pay && typeof rawData.krypton_pay === 'object' ? rawData.krypton_pay : null) as Record<string, unknown> | null
  const balanceOp = balanceSource?.operation ?? rawData?.operation ?? (p?.parsed_intent as Record<string, unknown>)?.operation
  const balancesArr = balanceSource?.balances ?? rawData?.balances
  const dailyArr = balanceSource?.dailyBalances ?? (balanceSource as Record<string, unknown>)?.daily_balances ?? rawData?.dailyBalances ?? rawData?.daily_balances
  const intradayArr = balanceSource?.intradayBalances ?? (balanceSource as Record<string, unknown>)?.intraday_balances ?? rawData?.intradayBalances ?? rawData?.intraday_balances
  const hasBalances = Array.isArray(balancesArr) && balancesArr.length > 0
  const hasDailyBalances = Array.isArray(dailyArr) && dailyArr.length > 0
  const hasIntradayBalances = Array.isArray(intradayArr) && intradayArr.length > 0
  const isBalanceOp = balanceOp === 'balances' || balanceOp === 'balances_daily' || balanceOp === 'balances_intraday'
  const hasBalanceKeys = rawData && (rawData.balances !== undefined || rawData.dailyBalances !== undefined || rawData.intradayBalances !== undefined || rawData.krypton_pay != null)
  const agentIds = (p?.parsed_intent as { agent_ids?: string[] } | undefined)?.agent_ids
  const hasKryptonPayBalance = Array.isArray(agentIds) && agentIds.includes('krypton_pay') && isBalanceOp
  const balanceResult = isBalanceOp && (hasBalances || hasDailyBalances || hasIntradayBalances || hasKryptonPayBalance || (hasBalanceKeys && balanceOp != null))
    ? {
        username_or_address: (balanceSource?.username_or_address ?? rawData?.username_or_address ?? (p?.parsed_intent as Record<string, unknown>)?.username_or_address ?? '') as string,
        operation: ((balanceOp as string) || 'balances') as 'balances' | 'balances_daily' | 'balances_intraday',
        ...(Array.isArray(balancesArr) && { balances: balancesArr }),
        ...(Array.isArray(dailyArr) && { dailyBalances: dailyArr }),
        ...(Array.isArray(intradayArr) && { intradayBalances: intradayArr }),
      }
    : undefined

  const screenerResult = rawData && rawData?.screener_type && rawData.screener_type !== 'economic'
    ? rawData
    : undefined
  const economicResult = rawData && rawData?.screener_type === 'economic' ? rawData : undefined

  const rawParameterRequest = p?.parameter_request as Record<string, unknown> | undefined
  const parameterRequest = rawParameterRequest
    ? {
        service: rawParameterRequest.service,
        actionType: rawParameterRequest.action_type,
        prompt: rawParameterRequest.prompt,
        missingParameters: (rawParameterRequest.missing_parameters ?? {}) as Record<string, unknown>,
        receivedParameters: (rawParameterRequest.received_parameters ?? {}) as Record<string, unknown>,
        requiredParameters: (rawParameterRequest.required_parameters ?? {}) as Record<string, unknown>,
        context: (rawParameterRequest.context ?? {}) as Record<string, unknown>,
      }
    : undefined

  return {
    id: messageId,
    type: 'assistant',
    content: responseMessage,
    timestamp: new Date(),
    parsedIntent: p?.parsed_intent,
    success: (p?.success ?? false) as boolean,
    backtestResult: backtestResult as ChatMessage['backtestResult'],
    priceHistoryResult: priceHistoryResult as ChatMessage['priceHistoryResult'],
    balanceResult: balanceResult as ChatMessage['balanceResult'],
    screenerResult: screenerResult as ChatMessage['screenerResult'],
    economicResult: economicResult as ChatMessage['economicResult'],
    regulationResult: regulationResult as ChatMessage['regulationResult'],
    source: (p?.source ?? rawData?.source) as string | undefined,
    capabilitiesSummary: (p?.capabilities_summary ?? rawData?.capabilities_summary) as string | undefined,
    parameterRequest: parameterRequest as ChatMessage['parameterRequest'],
    agentFlow: p?.agent_flow as ChatMessage['agentFlow'],
  }
}
