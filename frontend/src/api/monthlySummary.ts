export type CategorySpendingSummary = {
  category_id: string | null
  name: string
  color: string
  spent: string
}

export type BudgetProgressSummary = {
  budget_id: string
  category_id: string
  name: string
  color: string
  limit_amount: string
  spent: string
  remaining: string
  percent_used: string | null
  overspent: boolean
}

export type MonthlySummary = {
  month: string
  planned_income: string
  actual_inflows: string
  total_spending: string
  available_after_spending: string
  spending_percent: string | null
  remaining_percent: string | null
  uncategorized_count: number
  category_spending: CategorySpendingSummary[]
  budget_progress: BudgetProgressSummary[]
}

export async function getMonthlySummary(month: string): Promise<MonthlySummary> {
  const response = await fetch(`/api/v1/summary?month=${month}-01`)
  if (!response.ok) throw new Error('The monthly summary could not be loaded.')
  return (await response.json()) as MonthlySummary
}
