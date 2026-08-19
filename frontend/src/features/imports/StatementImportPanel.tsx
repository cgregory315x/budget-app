import { FormEvent, useCallback, useEffect, useState } from 'react'

import { Account, listAccounts } from '../../api/accounts'
import {
  CandidateTransactionPreview,
  StatementImportPreview,
  confirmStatementImport,
  previewStatement,
} from '../../api/imports'
import { emitDataChanged, onDataChanged } from '../../dataEvents'

function displayPeriod(preview: StatementImportPreview) {
  const { period_start: start, period_end: end } = preview.parsed_statement
  return start && end ? `${start} to ${end}` : 'Period unavailable'
}

export function StatementImportPanel() {
  const [accounts, setAccounts] = useState<Account[]>([])
  const [accountId, setAccountId] = useState('')
  const [file, setFile] = useState<File | null>(null)
  const [preview, setPreview] = useState<StatementImportPreview | null>(null)
  const [candidates, setCandidates] = useState<CandidateTransactionPreview[]>([])
  const [selected, setSelected] = useState<boolean[]>([])
  const [loading, setLoading] = useState(true)
  const [uploading, setUploading] = useState(false)
  const [confirming, setConfirming] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [success, setSuccess] = useState<string | null>(null)

  const loadSupportedAccounts = useCallback(async () => {
    const result = await listAccounts()
    const supported = result.filter((account) =>
      account.account_type === 'checking' || account.account_type === 'credit_card',
    )
    setAccounts(supported)
    setAccountId((current) =>
      supported.some((account) => account.id === current) ? current : supported[0]?.id ?? '',
    )
  }, [])

  useEffect(() => {
    let active = true
    listAccounts()
      .then((result) => {
        if (!active) return
        const supported = result.filter((account) =>
          account.account_type === 'checking' || account.account_type === 'credit_card',
        )
        setAccounts(supported)
        setAccountId(supported[0]?.id ?? '')
      })
      .catch((reason: unknown) => {
        if (active) setError(reason instanceof Error ? reason.message : 'Accounts could not be loaded.')
      })
      .finally(() => {
        if (active) setLoading(false)
      })
    return () => {
      active = false
    }
  }, [])

  useEffect(() => onDataChanged((scopes) => {
    if (!scopes.includes('accounts')) return
    void loadSupportedAccounts().catch((reason: unknown) => {
      setError(reason instanceof Error ? reason.message : 'Accounts could not be loaded.')
    })
  }), [loadSupportedAccounts])

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (!file || !accountId) return
    setUploading(true)
    setError(null)
    setSuccess(null)
    setPreview(null)
    try {
      const result = await previewStatement(accountId, file)
      setPreview(result)
      setCandidates(result.parsed_statement.transactions)
      setSelected(result.parsed_statement.transactions.map((row) => row.duplicate_status !== 'exact'))
    } catch (reason: unknown) {
      setError(reason instanceof Error ? reason.message : 'The statement could not be previewed.')
    } finally {
      setUploading(false)
    }
  }

  async function confirmImport() {
    if (!preview) return
    const approved = candidates.filter((_, index) => selected[index])
    if (approved.length === 0) return
    setConfirming(true)
    setError(null)
    setSuccess(null)
    try {
      const result = await confirmStatementImport({
        account_id: preview.account_id,
        adapter: preview.adapter,
        file_sha256: preview.statement.file_sha256,
        statement_start: preview.parsed_statement.period_start,
        statement_end: preview.parsed_statement.period_end,
        warnings: preview.parsed_statement.warnings,
        candidates: approved.map((candidate) => ({
          posted_date: candidate.posted_date,
          description: candidate.description,
          amount: candidate.amount,
          confidence: candidate.confidence,
          allow_duplicate: candidate.duplicate_status === 'exact',
        })),
      })
      setSuccess(
        `Imported ${result.transaction_count} transaction${result.transaction_count === 1 ? '' : 's'}.`,
      )
      emitDataChanged('transactions', 'summary')
    } catch (reason: unknown) {
      setError(reason instanceof Error ? reason.message : 'The statement could not be imported.')
    } finally {
      setConfirming(false)
    }
  }

  function updateCandidate(index: number, field: 'posted_date' | 'description' | 'amount', value: string) {
    setCandidates((current) => current.map((candidate, candidateIndex) =>
      candidateIndex === index ? { ...candidate, [field]: value } : candidate,
    ))
  }

  return (
    <section id="imports" className="panel import-panel" aria-labelledby="import-heading">
      <div className="panel-heading">
        <div>
          <p className="eyebrow">Milestone 2</p>
          <h2 id="import-heading">Preview a statement</h2>
          <p className="panel-description">
            Upload a selectable-text Navy Federal checking or credit-card PDF. Previewing does not create transactions.
          </p>
        </div>
      </div>

      <form className="import-form" onSubmit={submit}>
        <label>
          Statement account
          <select
            required
            value={accountId}
            disabled={loading || accounts.length === 0}
            onChange={(event) => setAccountId(event.target.value)}
          >
            {accounts.length === 0 && <option value="">No supported active accounts</option>}
            {accounts.map((account) => (
              <option key={account.id} value={account.id}>
                {account.name} ({account.account_type.replace('_', ' ')})
              </option>
            ))}
          </select>
        </label>
        <label>
          PDF statement
          <input
            required
            type="file"
            accept="application/pdf,.pdf"
            onChange={(event) => setFile(event.target.files?.[0] ?? null)}
          />
        </label>
        <button className="primary-button" type="submit" disabled={!accountId || !file || uploading}>
          {uploading ? 'Extracting…' : 'Preview text'}
        </button>
      </form>

      {error && <p className="form-error" role="alert">{error}</p>}
      {preview && (
        <div className="import-preview" aria-live="polite">
          <div className="import-metadata">
            <strong>{preview.statement.filename}</strong>
            <span>{preview.statement.page_count} page · {preview.statement.text_character_count} text characters</span>
            <span>Adapter: {preview.adapter}</span>
            <span>{preview.parsed_statement.institution}</span>
            <span>{displayPeriod(preview)}</span>
            {preview.parsed_statement.account_hint && (
              <span>Account {preview.parsed_statement.account_hint}</span>
            )}
          </div>
          {preview.statement.duplicate.is_duplicate && (
            <p className="duplicate-alert" role="status">
              This exact PDF matches a previously imported statement. Review candidates before continuing.
            </p>
          )}
          {preview.parsed_statement.warnings.length > 0 && (
            <ul className="import-warnings" aria-label="Statement warnings">
              {preview.parsed_statement.warnings.map((warning) => <li key={warning}>{warning}</li>)}
            </ul>
          )}
          <div className="candidate-table-wrap">
            {candidates.length === 0 ? (
              <p className="empty-state">
                No transaction rows were recognized. Review the extracted text below.
              </p>
            ) : <table className="candidate-table">
              <thead>
                <tr><th>Import</th><th>Date</th><th>Description</th><th>Amount</th><th>Review</th></tr>
              </thead>
              <tbody>
                {candidates.map((candidate, index) => (
                  <tr key={`${candidate.source_text}-${index}`}>
                    <td>
                      <input
                        aria-label={`Import transaction ${index + 1}`}
                        type="checkbox"
                        checked={selected[index] ?? false}
                        onChange={(event) => setSelected((current) => current.map(
                          (value, candidateIndex) => candidateIndex === index ? event.target.checked : value,
                        ))}
                      />
                    </td>
                    <td>
                      <input
                        aria-label={`Transaction ${index + 1} date`}
                        type="date"
                        value={candidate.posted_date}
                        onChange={(event) => updateCandidate(index, 'posted_date', event.target.value)}
                      />
                    </td>
                    <td>
                      <input
                        aria-label={`Transaction ${index + 1} description`}
                        value={candidate.description}
                        onChange={(event) => updateCandidate(index, 'description', event.target.value)}
                      />
                    </td>
                    <td>
                      <input
                        aria-label={`Transaction ${index + 1} amount`}
                        inputMode="decimal"
                        value={candidate.amount}
                        onChange={(event) => updateCandidate(index, 'amount', event.target.value)}
                      />
                    </td>
                    <td className={candidate.warnings.length > 0 ? 'candidate-warning' : ''}>
                      {candidate.warnings.length > 0
                        ? candidate.warnings.join(' · ')
                        : `${Math.round(Number(candidate.confidence) * 100)}% confidence`}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>}
          </div>
          <details open={candidates.length === 0}>
            <summary>View extracted statement text</summary>
            <pre>{preview.extracted_text}</pre>
          </details>
          <div className="confirm-actions">
            <button
              className="primary-button"
              type="button"
              disabled={
                confirming || success !== null || preview.statement.duplicate.is_duplicate
                || !selected.some(Boolean)
              }
              onClick={confirmImport}
            >
              {confirming ? 'Importing…' : 'Confirm selected transactions'}
            </button>
            <p className="preview-note">
              {selected.filter(Boolean).length} of {candidates.length} transactions selected.
            </p>
          </div>
          {success && <p className="import-success" role="status">{success}</p>}
        </div>
      )}
    </section>
  )
}
