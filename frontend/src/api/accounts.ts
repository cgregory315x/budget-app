export type AccountType = 'checking' | 'credit_card'

export type Account = {
  id: string
  name: string
  institution: string
  account_type: AccountType
  currency: string
  current_balance: string | null
  archived: boolean
  created_at: string
  updated_at: string
}

export type AccountInput = {
  name: string
  institution: string
  account_type: AccountType
  currency: string
  current_balance: string | null
}

type ApiErrorBody = { detail?: string }

async function request<T>(url: string, init?: RequestInit): Promise<T> {
  const response = await fetch(url, init)
  if (!response.ok) {
    let message = 'The account request failed.'
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

export function listAccounts(): Promise<Account[]> {
  return request<Account[]>('/api/v1/accounts')
}

export function createAccount(input: AccountInput): Promise<Account> {
  return request<Account>('/api/v1/accounts', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(input),
  })
}

export function updateAccount(id: string, input: AccountInput): Promise<Account> {
  return request<Account>(`/api/v1/accounts/${id}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(input),
  })
}

export function archiveAccount(id: string): Promise<void> {
  return request<void>(`/api/v1/accounts/${id}`, { method: 'DELETE' })
}
