export type MonthlyBudget = {
  id: string
  month: string
  category_id: string
  limit_amount: string
  created_at: string
  updated_at: string
}

export type MonthlyIncome = {
  id: string
  month: string
  description: string
  amount: string
  created_at: string
  updated_at: string
}

export type BudgetInput = {
  month: string
  category_id: string
  limit_amount: string
}

export type IncomeInput = {
  month: string
  description: string
  amount: string
}

type ApiErrorBody = { detail?: string }

async function request<T>(url: string, init?: RequestInit): Promise<T> {
  const response = await fetch(url, init)
  if (!response.ok) {
    let message = 'The monthly planning request failed.'
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

export function listBudgets(month: string): Promise<MonthlyBudget[]> {
  return request<MonthlyBudget[]>(`/api/v1/budgets?month=${month}-01`)
}

export function createBudget(input: BudgetInput): Promise<MonthlyBudget> {
  return request<MonthlyBudget>('/api/v1/budgets', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(input),
  })
}

export function updateBudget(id: string, input: BudgetInput): Promise<MonthlyBudget> {
  return request<MonthlyBudget>(`/api/v1/budgets/${id}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(input),
  })
}

export function deleteBudget(id: string): Promise<void> {
  return request<void>(`/api/v1/budgets/${id}`, { method: 'DELETE' })
}

export function listIncome(month: string): Promise<MonthlyIncome[]> {
  return request<MonthlyIncome[]>(`/api/v1/income?month=${month}-01`)
}

export function createIncome(input: IncomeInput): Promise<MonthlyIncome> {
  return request<MonthlyIncome>('/api/v1/income', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(input),
  })
}

export function updateIncome(id: string, input: IncomeInput): Promise<MonthlyIncome> {
  return request<MonthlyIncome>(`/api/v1/income/${id}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(input),
  })
}

export function deleteIncome(id: string): Promise<void> {
  return request<void>(`/api/v1/income/${id}`, { method: 'DELETE' })
}
