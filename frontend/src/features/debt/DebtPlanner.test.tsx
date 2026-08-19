import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { DebtPlanner } from './DebtPlanner'

const account = {
  id: 'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa',
  name: 'Synthetic Auto Loan',
  institution: 'Example Credit Union',
  account_type: 'loan',
  currency: 'USD',
  current_balance: '11480.25',
  archived: false,
  created_at: '2026-08-01T12:00:00Z',
  updated_at: '2026-08-01T12:00:00Z',
}

const loan = {
  id: 'bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb',
  account_id: account.id,
  principal: '12000.00',
  annual_rate_basis_points: 675,
  minimum_payment: '325.00',
  term_months: 48,
  created_at: '2026-08-01T12:00:00Z',
  updated_at: '2026-08-01T12:00:00Z',
}

const balance = {
  id: 'cccccccc-cccc-4ccc-8ccc-cccccccccccc',
  loan_terms_id: loan.id,
  as_of_date: '2026-08-01',
  balance: '11480.25',
  source: 'manual',
  created_at: '2026-08-01T12:00:00Z',
  updated_at: '2026-08-01T12:00:00Z',
}

const projection = {
  assumptions: {
    apr_treatment: 'Fixed nominal APR where 100 basis points equals 1% APR.',
    periodic_rate: 'APR divided by 12; no daily-interest calculation.',
    compounding: 'Interest compounds monthly.',
    payment_timing: "Monthly interest accrues before that month's payment.",
    currency_rounding: 'Interest and balances round to cents using ROUND_HALF_UP.',
    final_payment: 'The final payment is clamped to principal plus accrued interest.',
    maximum_months: 1200,
    disclaimer: 'Projections are estimates, not financial advice or payoff guarantees.',
  },
  payments: [{
    month: 1,
    payment_date: '2026-09-15',
    starting_balance: '11480.25',
    interest: '64.58',
    payment: '11544.83',
    principal: '11480.25',
    ending_balance: '0.00',
  }],
  total_interest: '64.58',
  total_paid: '11544.83',
  months: 1,
  payoff_date: '2026-09-15',
  annual_rate_basis_points: 675,
  monthly_rate: '0.005625',
}

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
  })
}

function debtFetch(includeDebt = true) {
  return vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
    const url = String(input)
    if (url === '/api/v1/accounts') return Promise.resolve(jsonResponse(includeDebt ? [account] : []))
    if (url === '/api/v1/loans') return Promise.resolve(jsonResponse(includeDebt ? [loan] : []))
    if (url.endsWith('/balances')) return Promise.resolve(jsonResponse([balance]))
    if (url === '/api/v1/debt/amortization' && init?.method === 'POST') {
      return Promise.resolve(jsonResponse(projection))
    }
    return Promise.reject(new Error(`Unexpected request: ${url}`))
  })
}

describe('DebtPlanner', () => {
  afterEach(() => {
    cleanup()
    vi.unstubAllGlobals()
  })

  it('shows actionable empty states when no loan account exists', async () => {
    vi.stubGlobal('fetch', debtFetch(false))
    render(<DebtPlanner />)

    expect(screen.getByText('Loading debt plan…')).toBeInTheDocument()
    expect(await screen.findByText(/Create a loan account before adding terms/)).toBeInTheDocument()
    expect(screen.getByText(/Select or add loan terms to record balances/)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Use selected loan' })).toBeDisabled()
  })

  it('displays saved loan terms and exact balance history', async () => {
    vi.stubGlobal('fetch', debtFetch())
    render(<DebtPlanner />)

    expect((await screen.findAllByText('Synthetic Auto Loan')).length).toBeGreaterThan(0)
    expect(await screen.findByText('$11,480.25')).toBeInTheDocument()
    expect(screen.getByText('2026-08-01 · manual')).toBeInTheDocument()
    expect(screen.getByText('$12,000.00 · 6.75% APR')).toBeInTheDocument()
  })

  it('renders assumptions, summary values, and an accessible exact-value schedule', async () => {
    vi.stubGlobal('fetch', debtFetch())
    render(<DebtPlanner />)

    await screen.findAllByText('Synthetic Auto Loan')
    await screen.findByText('$11,480.25')
    fireEvent.click(screen.getByRole('button', { name: 'Use selected loan' }))
    fireEvent.change(screen.getByLabelText('First payment date'), {
      target: { value: '2026-09-15' },
    })
    fireEvent.click(screen.getByRole('button', { name: 'Calculate payoff' }))

    expect((await screen.findAllByText('$11,544.83')).length).toBe(2)
    expect(screen.getByText(/ROUND_HALF_UP/)).toBeInTheDocument()
    expect(screen.getByText(/not financial advice/)).toBeInTheDocument()
    expect(screen.getByRole('table', { name: 'Exact month-by-month amortization schedule' })).toBeInTheDocument()
    expect(screen.getByLabelText('Amortization schedule, horizontally scrollable')).toHaveAttribute('tabindex', '0')
    expect(screen.getByRole('columnheader', { name: 'Ending balance' })).toBeInTheDocument()
    expect(screen.getByRole('cell', { name: '$0.00' })).toBeInTheDocument()
  })

  it('surfaces a sanitized debt API error', async () => {
    vi.stubGlobal('fetch', vi.fn((input: RequestInfo | URL) => {
      if (String(input) === '/api/v1/accounts') return Promise.resolve(jsonResponse([]))
      return Promise.resolve(jsonResponse({ detail: 'Debt service unavailable' }, 503))
    }))
    render(<DebtPlanner />)

    expect(await screen.findByRole('alert')).toHaveTextContent('Debt service unavailable')
  })
})
