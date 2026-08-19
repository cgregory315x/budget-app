import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { StatementImportPanel } from './StatementImportPanel'

const checkingAccount = {
  id: '51f64051-75f6-46fc-b209-4714b2286150',
  name: 'Synthetic Checking',
  institution: 'Synthetic Credit Union',
  account_type: 'checking',
  currency: 'USD',
  current_balance: null,
  archived: false,
  created_at: '2026-08-14T12:00:00Z',
  updated_at: '2026-08-14T12:00:00Z',
}

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } })
}

describe('StatementImportPanel', () => {
  afterEach(() => {
    cleanup()
    vi.unstubAllGlobals()
  })

  it('uploads a PDF and displays the extraction preview', async () => {
    const fetchMock = vi.fn()
      .mockResolvedValueOnce(jsonResponse([checkingAccount]))
      .mockResolvedValueOnce(jsonResponse({
        account_id: checkingAccount.id,
        adapter: 'navy_federal_checking_v1',
        statement: {
          filename: 'synthetic.pdf', content_type: 'application/pdf', size_bytes: 512,
          page_count: 1, text_character_count: 49,
        },
        extracted_text: 'NAVY FEDERAL CREDIT UNION Synthetic Statement',
      }))
    vi.stubGlobal('fetch', fetchMock)
    render(<StatementImportPanel />)

    await screen.findByRole('option', { name: 'Synthetic Checking' })
    const file = new File(['%PDF- synthetic'], 'synthetic.pdf', { type: 'application/pdf' })
    fireEvent.change(screen.getByLabelText('PDF statement'), { target: { files: [file] } })
    fireEvent.submit(screen.getByRole('button', { name: 'Preview text' }).closest('form')!)

    expect(await screen.findByText('Adapter: navy_federal_checking_v1')).toBeInTheDocument()
    expect(screen.getByText(/NAVY FEDERAL CREDIT UNION/)).toBeInTheDocument()
    const [, request] = fetchMock.mock.calls[1]
    expect(fetchMock.mock.calls[1][0]).toBe('/api/v1/imports/preview')
    expect(request).toEqual(expect.objectContaining({ method: 'POST', body: expect.any(FormData) }))
  })

  it('shows server validation errors', async () => {
    vi.stubGlobal('fetch', vi.fn()
      .mockResolvedValueOnce(jsonResponse([checkingAccount]))
      .mockResolvedValueOnce(jsonResponse({ detail: 'PDF must contain non-empty selectable text' }, 422)))
    render(<StatementImportPanel />)

    await screen.findByRole('option', { name: 'Synthetic Checking' })
    fireEvent.change(screen.getByLabelText('PDF statement'), {
      target: { files: [new File(['%PDF-'], 'scan.pdf', { type: 'application/pdf' })] },
    })
    fireEvent.submit(screen.getByRole('button', { name: 'Preview text' }).closest('form')!)

    await waitFor(() => expect(screen.getByRole('alert')).toHaveTextContent('non-empty selectable text'))
  })
})
