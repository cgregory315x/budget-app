export type Transaction = {
  id: string
  account_id: string
  category_id: string | null
  categorization_source: 'manual' | 'merchant_rule' | null
  categorization_rule_id: string | null
  posted_date: string
  description: string
  amount: string
  excluded_from_budget: boolean
  created_at: string
  updated_at: string
}

export type TransactionInput = {
  account_id: string
  category_id: string | null
  posted_date: string
  description: string
  amount: string
  excluded_from_budget: boolean
}

export type TransactionFilters = {
  account_id?: string
  category_id?: string
  uncategorized?: boolean
  posted_from?: string
  posted_to?: string
  search?: string
}

type ApiErrorBody = { detail?: string }

async function request<T>(url: string, init?: RequestInit): Promise<T> {
  const response = await fetch(url, init)
  if (!response.ok) {
    let message = 'The transaction request failed.'
    try {
      const body = (await response.json()) as ApiErrorBody
      if (typeof body.detail === 'string') message = body.detail
    } catch {
      // Keep the generic message when an intermediary returns a non-JSON response.
    }
    throw new Error(message)
  }
  if (response.status === 204) return undefined as T
  return (await response.json()) as T
}

export function listTransactions(filters: TransactionFilters = {}): Promise<Transaction[]> {
  const query = new URLSearchParams()
  Object.entries(filters).forEach(([key, value]) => {
    if (value !== undefined && value !== '') query.set(key, String(value))
  })
  const suffix = query.size ? `?${query.toString()}` : ''
  return request<Transaction[]>(`/api/v1/transactions${suffix}`)
}

export function createTransaction(input: TransactionInput): Promise<Transaction> {
  return request<Transaction>('/api/v1/transactions', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(input),
  })
}

export function updateTransaction(id: string, input: TransactionInput): Promise<Transaction> {
  return request<Transaction>(`/api/v1/transactions/${id}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(input),
  })
}

export function deleteTransaction(id: string): Promise<void> {
  return request<void>(`/api/v1/transactions/${id}`, { method: 'DELETE' })
}
