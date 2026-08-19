import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { emitDataChanged } from '../../dataEvents'
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
          file_sha256: 'a'.repeat(64),
          duplicate: { is_duplicate: true, existing_import_id: 'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa' },
        },
        parsed_statement: {
          institution: 'Navy Federal Credit Union', account_hint: '…1234',
          period_start: '2026-08-01', period_end: '2026-08-31', warnings: [],
          transactions: [{
            posted_date: '2026-08-02', description: 'SYNTHETIC MARKET', amount: '-45.67',
            source_text: '08/02/2026 SYNTHETIC MARKET -45.67', confidence: '1.000',
            warnings: ['Exact duplicate of an existing transaction'], duplicate_status: 'exact',
            matched_transaction_id: 'bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb',
          }],
        },
        extracted_text: 'NAVY FEDERAL CREDIT UNION Synthetic Statement',
      }))
    vi.stubGlobal('fetch', fetchMock)
    render(<StatementImportPanel />)

    await screen.findByRole('option', { name: 'Synthetic Checking (checking)' })
    const file = new File(['%PDF- synthetic'], 'synthetic.pdf', { type: 'application/pdf' })
    fireEvent.change(screen.getByLabelText('PDF statement'), { target: { files: [file] } })
    fireEvent.submit(screen.getByRole('button', { name: 'Preview text' }).closest('form')!)

    expect(await screen.findByText('Adapter: navy_federal_checking_v1')).toBeInTheDocument()
    expect(screen.getByText('Navy Federal Credit Union')).toBeInTheDocument()
    expect(screen.getByDisplayValue('SYNTHETIC MARKET')).toBeInTheDocument()
    expect(screen.getByText(/matches a previously imported statement/)).toBeInTheDocument()
    expect(screen.getByText('Exact duplicate of an existing transaction')).toBeInTheDocument()
    fireEvent.change(screen.getByLabelText('Transaction 1 description'), {
      target: { value: 'EDITED SYNTHETIC MARKET' },
    })
    expect(screen.getByDisplayValue('EDITED SYNTHETIC MARKET')).toBeInTheDocument()
    const [, request] = fetchMock.mock.calls[1]
    expect(fetchMock.mock.calls[1][0]).toBe('/api/v1/imports/preview')
    expect(request).toEqual(expect.objectContaining({ method: 'POST', body: expect.any(FormData) }))
  })

  it('shows server validation errors', async () => {
    vi.stubGlobal('fetch', vi.fn()
      .mockResolvedValueOnce(jsonResponse([checkingAccount]))
      .mockResolvedValueOnce(jsonResponse({ detail: 'PDF must contain non-empty selectable text' }, 422)))
    render(<StatementImportPanel />)

    await screen.findByRole('option', { name: 'Synthetic Checking (checking)' })
    fireEvent.change(screen.getByLabelText('PDF statement'), {
      target: { files: [new File(['%PDF-'], 'scan.pdf', { type: 'application/pdf' })] },
    })
    fireEvent.submit(screen.getByRole('button', { name: 'Preview text' }).closest('form')!)

    await waitFor(() => expect(screen.getByRole('alert')).toHaveTextContent('non-empty selectable text'))
  })

  it('shows extracted text when no transaction rows are recognized', async () => {
    vi.stubGlobal('fetch', vi.fn()
      .mockResolvedValueOnce(jsonResponse([checkingAccount]))
      .mockResolvedValueOnce(jsonResponse({
        account_id: checkingAccount.id,
        adapter: 'navy_federal_checking_v1',
        statement: {
          filename: 'statement.pdf', content_type: 'application/pdf', size_bytes: 512,
          page_count: 1, text_character_count: 42,
          file_sha256: 'b'.repeat(64),
          duplicate: { is_duplicate: false, existing_import_id: null },
        },
        parsed_statement: {
          institution: 'Navy Federal Credit Union', account_hint: null,
          period_start: null, period_end: null, transactions: [],
          warnings: ['Transaction parser needs review: No supported transaction rows were found'],
        },
        extracted_text: 'NAVY FEDERAL CREDIT UNION\nActual extracted layout',
      })))
    render(<StatementImportPanel />)

    await screen.findByRole('option', { name: 'Synthetic Checking (checking)' })
    fireEvent.change(screen.getByLabelText('PDF statement'), {
      target: { files: [new File(['%PDF-'], 'statement.pdf', { type: 'application/pdf' })] },
    })
    fireEvent.submit(screen.getByRole('button', { name: 'Preview text' }).closest('form')!)

    expect(await screen.findByText(/No transaction rows were recognized/)).toBeInTheDocument()
    expect(screen.getByText(/Actual extracted layout/)).toBeInTheDocument()
  })

  it('confirms selected candidate transactions', async () => {
    const fetchMock = vi.fn()
      .mockResolvedValueOnce(jsonResponse([checkingAccount]))
      .mockResolvedValueOnce(jsonResponse({
        account_id: checkingAccount.id,
        adapter: 'navy_federal_checking_v1',
        statement: {
          filename: 'statement.pdf', content_type: 'application/pdf', size_bytes: 512,
          page_count: 1, text_character_count: 42, file_sha256: 'c'.repeat(64),
          duplicate: { is_duplicate: false, existing_import_id: null },
        },
        parsed_statement: {
          institution: 'Navy Federal Credit Union', account_hint: '…1234',
          period_start: '2026-08-01', period_end: '2026-08-31', warnings: [],
          transactions: [{
            posted_date: '2026-08-02', description: 'SYNTHETIC MARKET', amount: '-45.67',
            source_text: '08/02/2026 SYNTHETIC MARKET -45.67', confidence: '1.000',
            warnings: [], duplicate_status: null, matched_transaction_id: null,
          }],
        },
        extracted_text: 'NAVY FEDERAL CREDIT UNION\nSynthetic statement',
      }))
      .mockResolvedValueOnce(jsonResponse({
        import_id: 'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa',
        transaction_ids: ['bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb'],
        transaction_count: 1,
      }))
    vi.stubGlobal('fetch', fetchMock)
    render(<StatementImportPanel />)

    await screen.findByRole('option', { name: 'Synthetic Checking (checking)' })
    fireEvent.change(screen.getByLabelText('PDF statement'), {
      target: { files: [new File(['%PDF-'], 'statement.pdf', { type: 'application/pdf' })] },
    })
    fireEvent.submit(screen.getByRole('button', { name: 'Preview text' }).closest('form')!)
    await screen.findByDisplayValue('SYNTHETIC MARKET')
    fireEvent.click(screen.getByRole('button', { name: 'Confirm selected transactions' }))

    expect(await screen.findByText('Imported 1 transaction.')).toBeInTheDocument()
    expect(fetchMock).toHaveBeenLastCalledWith(
      '/api/v1/imports/confirm',
      expect.objectContaining({ method: 'POST' }),
    )
    const confirmBody = JSON.parse(fetchMock.mock.calls[2][1].body as string)
    expect(confirmBody.candidates).toEqual([
      expect.objectContaining({ description: 'SYNTHETIC MARKET', allow_duplicate: false }),
    ])
  })

  it('reloads the account selector when accounts change', async () => {
    const fetchMock = vi.fn()
      .mockResolvedValueOnce(jsonResponse([]))
      .mockResolvedValueOnce(jsonResponse([checkingAccount]))
    vi.stubGlobal('fetch', fetchMock)
    render(<StatementImportPanel />)

    await screen.findByRole('option', { name: 'No supported active accounts' })
    emitDataChanged('accounts')

    expect(
      await screen.findByRole('option', { name: 'Synthetic Checking (checking)' }),
    ).toBeInTheDocument()
    expect(fetchMock).toHaveBeenCalledTimes(2)
  })
})
