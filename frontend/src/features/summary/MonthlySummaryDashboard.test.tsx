import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { emitDataChanged } from '../../dataEvents'
import { MonthlySummaryDashboard } from './MonthlySummaryDashboard'

const summary = {
  month: '2026-08-01',
  planned_income: '2000.00',
  actual_inflows: '1500.00',
  total_spending: '110.00',
  available_after_spending: '1890.00',
  spending_percent: '5.5',
  remaining_percent: '94.5',
  uncategorized_count: 2,
  category_spending: [
    {
      category_id: 'eef5b14c-7d2d-44b1-87c2-efdf16ce144b',
      name: 'Synthetic Groceries',
      color: '#397D72',
      spent: '80.00',
    },
    { category_id: null, name: 'Uncategorized', color: '#A3AAA7', spent: '30.00' },
  ],
  budget_progress: [
    {
      budget_id: '7ab38dd5-cebe-48a0-b028-a4e18fb063af',
      category_id: 'eef5b14c-7d2d-44b1-87c2-efdf16ce144b',
      name: 'Synthetic Groceries',
      color: '#397D72',
      limit_amount: '75.00',
      spent: '80.00',
      remaining: '-5.00',
      percent_used: '106.7',
      overspent: true,
    },
  ],
}

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
  })
}

describe('MonthlySummaryDashboard', () => {
  afterEach(() => {
    cleanup()
    vi.unstubAllGlobals()
  })

  it('renders real monthly totals and review count', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(jsonResponse(summary)))
    render(<MonthlySummaryDashboard />)

    expect(await screen.findByText('$1,890.00')).toBeInTheDocument()
    expect(screen.getByText('$2,000.00')).toBeInTheDocument()
    expect(screen.getByText('$1,500.00 in recorded inflows')).toBeInTheDocument()
    expect(screen.getAllByText('$110.00')).toHaveLength(2)
    expect(screen.getByText('94.5% of income remains')).toBeInTheDocument()
    expect(screen.getByText('2')).toBeInTheDocument()
  })

  it('renders budget progress and spending composition', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(jsonResponse(summary)))
    render(<MonthlySummaryDashboard />)

    expect(await screen.findAllByText('Synthetic Groceries')).toHaveLength(2)
    expect(screen.getByLabelText('$80.00 spent of $75.00')).toBeInTheDocument()
    expect(screen.getByText('Uncategorized')).toBeInTheDocument()
    expect(
      screen.getByRole('img', { name: 'Spending composition totaling $110.00' }),
    ).toBeInTheDocument()
  })

  it('reloads the selected month', async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(jsonResponse(summary))
      .mockResolvedValueOnce(jsonResponse({ ...summary, month: '2026-09-01' }))
    vi.stubGlobal('fetch', fetchMock)
    render(<MonthlySummaryDashboard />)

    await screen.findByText('$1,890.00')
    fireEvent.change(screen.getByLabelText('Month'), { target: { value: '2026-09' } })

    expect(await screen.findByText('September 2026')).toBeInTheDocument()
    expect(fetchMock).toHaveBeenLastCalledWith('/api/v1/summary?month=2026-09-01')
  })

  it('shows a safe error state', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(jsonResponse({}, 503)))
    render(<MonthlySummaryDashboard />)

    expect(await screen.findByRole('alert')).toHaveTextContent(
      'The monthly summary could not be loaded.',
    )
  })

  it('reloads after transaction data changes', async () => {
    const fetchMock = vi.fn()
      .mockResolvedValueOnce(jsonResponse(summary))
      .mockResolvedValueOnce(jsonResponse({
        ...summary,
        available_after_spending: '1800.00',
        total_spending: '200.00',
      }))
    vi.stubGlobal('fetch', fetchMock)
    render(<MonthlySummaryDashboard />)

    await screen.findByText('$1,890.00')
    emitDataChanged('summary')

    expect(await screen.findByText('$1,800.00')).toBeInTheDocument()
    expect(fetchMock).toHaveBeenCalledTimes(2)
  })
})
