export type LoanTerms = {
  id: string
  account_id: string
  principal: string
  annual_rate_basis_points: number
  minimum_payment: string
  term_months: number | null
  created_at: string
  updated_at: string
}

export type LoanTermsInput = Omit<LoanTerms, 'id' | 'created_at' | 'updated_at'>

export type LoanBalance = {
  id: string
  loan_terms_id: string
  as_of_date: string
  balance: string
  source: string
  created_at: string
  updated_at: string
}

export type LoanBalanceInput = Pick<LoanBalance, 'as_of_date' | 'balance' | 'source'>

export type ProjectionAssumptions = {
  apr_treatment: string
  periodic_rate: string
  compounding: string
  payment_timing: string
  currency_rounding: string
  final_payment: string
  maximum_months: number
  disclaimer: string
}

export type AmortizationPayment = {
  month: number
  payment_date: string
  starting_balance: string
  interest: string
  payment: string
  principal: string
  ending_balance: string
}

export type AmortizationProjection = {
  assumptions: ProjectionAssumptions
  payments: AmortizationPayment[]
  total_interest: string
  total_paid: string
  months: number
  payoff_date: string | null
  annual_rate_basis_points: number
  monthly_rate: string
}

export type AmortizationInput = {
  principal: string
  annual_rate_basis_points: number
  monthly_payment: string
  first_payment_date: string
}

type ApiErrorBody = { detail?: string }

async function request<T>(url: string, init?: RequestInit): Promise<T> {
  const response = await fetch(url, init)
  if (!response.ok) {
    let message = 'The debt request failed.'
    try {
      const body = (await response.json()) as ApiErrorBody
      if (typeof body.detail === 'string') message = body.detail
    } catch {
      // Keep the generic message for non-JSON failures.
    }
    throw new Error(message)
  }
  if (response.status === 204) return undefined as T
  return (await response.json()) as T
}

const json = (method: string, body: unknown): RequestInit => ({
  method,
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify(body),
})

export const listLoans = () => request<LoanTerms[]>('/api/v1/loans')
export const createLoan = (input: LoanTermsInput) =>
  request<LoanTerms>('/api/v1/loans', json('POST', input))
export const updateLoan = (id: string, input: Partial<LoanTermsInput>) =>
  request<LoanTerms>(`/api/v1/loans/${id}`, json('PATCH', input))
export const deleteLoan = (id: string) =>
  request<void>(`/api/v1/loans/${id}`, { method: 'DELETE' })

export const listLoanBalances = (loanId: string) =>
  request<LoanBalance[]>(`/api/v1/loans/${loanId}/balances`)
export const createLoanBalance = (loanId: string, input: LoanBalanceInput) =>
  request<LoanBalance>(`/api/v1/loans/${loanId}/balances`, json('POST', input))
export const updateLoanBalance = (loanId: string, balanceId: string, input: LoanBalanceInput) =>
  request<LoanBalance>(
    `/api/v1/loans/${loanId}/balances/${balanceId}`,
    json('PATCH', input),
  )
export const deleteLoanBalance = (loanId: string, balanceId: string) =>
  request<void>(`/api/v1/loans/${loanId}/balances/${balanceId}`, { method: 'DELETE' })

export const projectAmortization = (input: AmortizationInput) =>
  request<AmortizationProjection>('/api/v1/debt/amortization', json('POST', input))
