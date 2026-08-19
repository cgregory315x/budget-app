import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { emitDataChanged } from '../../dataEvents'
import { TransactionManager } from './TransactionManager'

const account = {
  id: '51f64051-75f6-46fc-b209-4714b2286150',
  name: 'Synthetic Checking',
  institution: 'Example Credit Union',
  account_type: 'checking',
  currency: 'USD',
  current_balance: '1250.25',
  archived: false,
  created_at: '2026-08-14T12:00:00Z',
  updated_at: '2026-08-14T12:00:00Z',
}

const category = {
  id: 'eef5b14c-7d2d-44b1-87c2-efdf16ce144b',
  name: 'Synthetic Groceries',
  kind: 'expense',
  color: '#397D72',
  archived: false,
  created_at: '2026-08-14T12:00:00Z',
  updated_at: '2026-08-14T12:00:00Z',
}

const transaction = {
  id: 'f61ae2fd-013b-45cb-97f3-8de6dbabddad',
  account_id: account.id,
  category_id: category.id,
  categorization_source: 'merchant_rule',
  categorization_rule_id: 'b834222b-672a-477b-af84-0fd1ad437aad',
  posted_date: '2026-08-14',
  description: 'Example Market',
  amount: '-42.15',
  excluded_from_budget: false,
  created_at: '2026-08-14T12:00:00Z',
  updated_at: '2026-08-14T12:00:00Z',
}

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
  })
}

function initialFetch(transactions: unknown[] = []) {
  return vi
    .fn()
    .mockResolvedValueOnce(jsonResponse([account]))
    .mockResolvedValueOnce(jsonResponse([category]))
    .mockResolvedValueOnce(jsonResponse(transactions))
}

describe('TransactionManager', () => {
  afterEach(() => {
    cleanup()
    vi.unstubAllGlobals()
  })

  it('loads and displays categorized transactions', async () => {
    vi.stubGlobal('fetch', initialFetch([transaction]))
    render(<TransactionManager />)

    expect(await screen.findByText('Example Market')).toBeInTheDocument()
    expect(screen.getAllByText('Synthetic Groceries')).toHaveLength(3)
    expect(screen.getByText('-$42.15')).toBeInTheDocument()
    expect(screen.getByText('Merchant rule')).toBeInTheDocument()
  })

  it('creates a manual transaction and refreshes the ledger', async () => {
    const fetchMock = initialFetch()
      .mockResolvedValueOnce(jsonResponse(transaction, 201))
      .mockResolvedValueOnce(jsonResponse([transaction]))
    vi.stubGlobal('fetch', fetchMock)
    render(<TransactionManager />)

    await screen.findByText(/No transactions match/)
    fireEvent.change(screen.getByLabelText('Description'), {
      target: { value: 'Example Market' },
    })
    fireEvent.change(screen.getByLabelText('Amount'), { target: { value: '-42.15' } })
    fireEvent.click(screen.getByRole('button', { name: 'Add transaction' }))

    expect(await screen.findByText('Example Market')).toBeInTheDocument()
    expect(fetchMock).toHaveBeenNthCalledWith(
      4,
      '/api/v1/transactions',
      expect.objectContaining({ method: 'POST' }),
    )
  })

  it('applies the uncategorized and description filters', async () => {
    const fetchMock = initialFetch().mockResolvedValueOnce(jsonResponse([]))
    vi.stubGlobal('fetch', fetchMock)
    render(<TransactionManager />)

    await screen.findByText(/No transactions match/)
    fireEvent.change(screen.getByLabelText('Search descriptions'), {
      target: { value: 'market' },
    })
    fireEvent.change(screen.getByLabelText('Filter by category'), {
      target: { value: 'uncategorized' },
    })
    fireEvent.click(screen.getByRole('button', { name: 'Apply filters' }))

    await waitFor(() => {
      expect(fetchMock).toHaveBeenLastCalledWith(
        '/api/v1/transactions?search=market&uncategorized=true',
        undefined,
      )
    })
  })

  it('deletes a transaction after confirmation', async () => {
    const fetchMock = initialFetch([transaction])
      .mockResolvedValueOnce(new Response(null, { status: 204 }))
      .mockResolvedValueOnce(jsonResponse([]))
    vi.stubGlobal('fetch', fetchMock)
    vi.stubGlobal('confirm', vi.fn(() => true))
    render(<TransactionManager />)

    await screen.findByText('Example Market')
    fireEvent.click(screen.getByRole('button', { name: 'Delete' }))

    expect(await screen.findByText(/No transactions match/)).toBeInTheDocument()
    expect(fetchMock).toHaveBeenNthCalledWith(
      4,
      `/api/v1/transactions/${transaction.id}`,
      { method: 'DELETE' },
    )
  })

  it('reloads the ledger when imported transactions change', async () => {
    const fetchMock = initialFetch().mockResolvedValueOnce(jsonResponse([transaction]))
    vi.stubGlobal('fetch', fetchMock)
    render(<TransactionManager />)

    await screen.findByText(/No transactions match/)
    emitDataChanged('transactions')

    expect(await screen.findByText('Example Market')).toBeInTheDocument()
    expect(fetchMock).toHaveBeenCalledTimes(4)
  })

  it('reloads category dropdowns when categories change', async () => {
    const food = { ...category, id: '11111111-1111-1111-1111-111111111111', name: 'Food' }
    const fetchMock = initialFetch().mockResolvedValueOnce(jsonResponse([category, food]))
    vi.stubGlobal('fetch', fetchMock)
    render(<TransactionManager />)

    await screen.findByText(/No transactions match/)
    emitDataChanged('categories')

    expect(await screen.findAllByRole('option', { name: 'Food' })).toHaveLength(2)
  })
})
