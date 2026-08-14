import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { MonthlyPlanManager } from './MonthlyPlanManager'

const category = {
  id: 'eef5b14c-7d2d-44b1-87c2-efdf16ce144b',
  name: 'Synthetic Groceries',
  kind: 'expense',
  color: '#397D72',
  archived: false,
  created_at: '2026-08-14T12:00:00Z',
  updated_at: '2026-08-14T12:00:00Z',
}

const budget = {
  id: '7ab38dd5-cebe-48a0-b028-a4e18fb063af',
  month: '2026-08-01',
  category_id: category.id,
  limit_amount: '450.00',
  created_at: '2026-08-14T12:00:00Z',
  updated_at: '2026-08-14T12:00:00Z',
}

const income = {
  id: 'e3616ad7-cee4-4d2a-aeed-a2821fc177a4',
  month: '2026-08-01',
  description: 'Synthetic Paycheck',
  amount: '3200.00',
  created_at: '2026-08-14T12:00:00Z',
  updated_at: '2026-08-14T12:00:00Z',
}

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
  })
}

function initialFetch(budgets: unknown[] = [], incomeEntries: unknown[] = []) {
  return vi
    .fn()
    .mockResolvedValueOnce(jsonResponse([category]))
    .mockResolvedValueOnce(jsonResponse(budgets))
    .mockResolvedValueOnce(jsonResponse(incomeEntries))
}

describe('MonthlyPlanManager', () => {
  afterEach(() => {
    cleanup()
    vi.unstubAllGlobals()
  })

  it('loads budgets, income, and monthly totals', async () => {
    vi.stubGlobal('fetch', initialFetch([budget], [income]))
    render(<MonthlyPlanManager />)

    expect(await screen.findAllByText('Synthetic Groceries')).toHaveLength(2)
    expect(screen.getByText('Synthetic Paycheck')).toBeInTheDocument()
    expect(screen.getAllByText('$450.00')).toHaveLength(2)
    expect(screen.getAllByText('$3,200.00')).toHaveLength(2)
  })

  it('creates a category budget and refreshes the month', async () => {
    const fetchMock = initialFetch()
      .mockResolvedValueOnce(jsonResponse(budget, 201))
      .mockResolvedValueOnce(jsonResponse([budget]))
      .mockResolvedValueOnce(jsonResponse([]))
    vi.stubGlobal('fetch', fetchMock)
    render(<MonthlyPlanManager />)

    await screen.findAllByText('$0.00')
    fireEvent.change(screen.getByLabelText('Budget limit'), { target: { value: '450.00' } })
    fireEvent.click(screen.getAllByRole('button', { name: 'Add' })[0])

    expect(await screen.findAllByText('$450.00')).toHaveLength(2)
    expect(fetchMock).toHaveBeenNthCalledWith(
      4,
      '/api/v1/budgets',
      expect.objectContaining({ method: 'POST' }),
    )
  })

  it('creates an expected income entry and refreshes the month', async () => {
    const fetchMock = initialFetch()
      .mockResolvedValueOnce(jsonResponse(income, 201))
      .mockResolvedValueOnce(jsonResponse([]))
      .mockResolvedValueOnce(jsonResponse([income]))
    vi.stubGlobal('fetch', fetchMock)
    render(<MonthlyPlanManager />)

    await screen.findAllByText('$0.00')
    fireEvent.change(screen.getByLabelText('Income description'), {
      target: { value: 'Synthetic Paycheck' },
    })
    fireEvent.change(screen.getByLabelText('Income amount'), { target: { value: '3200.00' } })
    fireEvent.click(screen.getAllByRole('button', { name: 'Add' })[1])

    expect(await screen.findByText('Synthetic Paycheck')).toBeInTheDocument()
    expect(fetchMock).toHaveBeenNthCalledWith(
      4,
      '/api/v1/income',
      expect.objectContaining({ method: 'POST' }),
    )
  })

  it('reloads entries when the selected month changes', async () => {
    const fetchMock = initialFetch()
      .mockResolvedValueOnce(jsonResponse([category]))
      .mockResolvedValueOnce(jsonResponse([]))
      .mockResolvedValueOnce(jsonResponse([]))
    vi.stubGlobal('fetch', fetchMock)
    render(<MonthlyPlanManager />)

    await screen.findAllByText('$0.00')
    fireEvent.change(screen.getByLabelText('Month'), { target: { value: '2026-09' } })

    await screen.findAllByText('$0.00')
    expect(fetchMock).toHaveBeenCalledWith('/api/v1/budgets?month=2026-09-01', undefined)
    expect(fetchMock).toHaveBeenCalledWith('/api/v1/income?month=2026-09-01', undefined)
  })
})
