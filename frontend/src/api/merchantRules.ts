export type MatchType = 'exact' | 'contains' | 'regex'

export type MerchantRule = {
  id: string
  pattern: string
  pattern_normalized: string
  match_type: MatchType
  category_id: string
  priority: number
  enabled: boolean
}

export type MerchantRuleInput = Omit<MerchantRule, 'id' | 'pattern_normalized'>

export type RuleMatch = {
  transaction_id: string
  description: string
  merchant_normalized: string
  posted_date: string
  amount: string
  rule_id: string
  rule_pattern: string
  category_id: string
  category_name: string
  competing_rule_ids: string[]
}

type Preview = { matches: RuleMatch[]; unmatched_count: number }
type ApplyResult = { applied_count: number; skipped_count: number }

async function request<T>(url: string, init?: RequestInit): Promise<T> {
  const response = await fetch(url, init)
  if (!response.ok) {
    let message = 'The merchant-rule request failed.'
    try {
      const body = (await response.json()) as { detail?: string }
      if (typeof body.detail === 'string') message = body.detail
    } catch { /* retain safe generic error */ }
    throw new Error(message)
  }
  if (response.status === 204) return undefined as T
  return response.json() as Promise<T>
}

const json = (method: string, body?: unknown): RequestInit => ({
  method,
  headers: { 'Content-Type': 'application/json' },
  body: body === undefined ? undefined : JSON.stringify(body),
})

export const listMerchantRules = () => request<MerchantRule[]>('/api/v1/merchant-rules')
export const createMerchantRule = (input: MerchantRuleInput) =>
  request<MerchantRule>('/api/v1/merchant-rules', json('POST', input))
export const updateMerchantRule = (id: string, input: Partial<MerchantRuleInput>) =>
  request<MerchantRule>(`/api/v1/merchant-rules/${id}`, json('PATCH', input))
export const disableMerchantRule = (id: string) =>
  request<MerchantRule>(`/api/v1/merchant-rules/${id}/disable`, json('POST'))
export const deleteMerchantRule = (id: string) =>
  request<void>(`/api/v1/merchant-rules/${id}`, { method: 'DELETE' })
export const previewMerchantMatches = () =>
  request<Preview>('/api/v1/merchant-rules/matches/preview', json('POST'))
export const applyMerchantMatches = (transactionIds: string[]) =>
  request<ApplyResult>('/api/v1/merchant-rules/matches/apply', json('POST', { transaction_ids: transactionIds }))
