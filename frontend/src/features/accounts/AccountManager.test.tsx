import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { AccountManager } from './AccountManager'

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

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
  })
}

describe('AccountManager', () => {
  afterEach(() => {
    cleanup()
    vi.unstubAllGlobals()
  })

  it('shows the empty state after loading', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(jsonResponse([])))
    render(<AccountManager />)

    expect(screen.getByText('Loading accounts…')).toBeInTheDocument()
    expect(await screen.findByText(/No accounts yet/)).toBeInTheDocument()
  })

  it('creates and displays an account', async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(jsonResponse([]))
      .mockResolvedValueOnce(jsonResponse(account, 201))
    vi.stubGlobal('fetch', fetchMock)
    render(<AccountManager />)

    await screen.findByText(/No accounts yet/)
    fireEvent.change(screen.getByLabelText('Name'), {
      target: { value: 'Synthetic Checking' },
    })
    fireEvent.change(screen.getByLabelText('Institution'), {
      target: { value: 'Example Credit Union' },
    })
    fireEvent.click(screen.getByRole('button', { name: 'Add account' }))

    expect(await screen.findByText('Synthetic Checking')).toBeInTheDocument()
    expect(screen.getByText('$1,250.25')).toBeInTheDocument()
    expect(fetchMock).toHaveBeenLastCalledWith(
      '/api/v1/accounts',
      expect.objectContaining({ method: 'POST' }),
    )
  })

  it('archives an account from the active list', async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(jsonResponse([account]))
      .mockResolvedValueOnce(new Response(null, { status: 204 }))
    vi.stubGlobal('fetch', fetchMock)
    render(<AccountManager />)

    await screen.findByText('Synthetic Checking')
    fireEvent.click(screen.getByRole('button', { name: 'Archive' }))

    await waitFor(() => expect(screen.queryByText('Synthetic Checking')).not.toBeInTheDocument())
    expect(screen.getByText(/No accounts yet/)).toBeInTheDocument()
  })

  it('surfaces a sanitized API error', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(jsonResponse({ detail: 'Account service unavailable' }, 503)),
    )
    render(<AccountManager />)

    expect(await screen.findByRole('alert')).toHaveTextContent('Account service unavailable')
  })
})
