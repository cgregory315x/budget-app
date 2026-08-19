import { FormEvent, useEffect, useState } from 'react'

import { Account, listAccounts } from '../../api/accounts'
import { StatementImportPreview, previewStatement } from '../../api/imports'

export function StatementImportPanel() {
  const [accounts, setAccounts] = useState<Account[]>([])
  const [accountId, setAccountId] = useState('')
  const [file, setFile] = useState<File | null>(null)
  const [preview, setPreview] = useState<StatementImportPreview | null>(null)
  const [loading, setLoading] = useState(true)
  const [uploading, setUploading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let active = true
    listAccounts()
      .then((result) => {
        if (!active) return
        const checking = result.filter((account) => account.account_type === 'checking')
        setAccounts(checking)
        setAccountId(checking[0]?.id ?? '')
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

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (!file || !accountId) return
    setUploading(true)
    setError(null)
    setPreview(null)
    try {
      setPreview(await previewStatement(accountId, file))
    } catch (reason: unknown) {
      setError(reason instanceof Error ? reason.message : 'The statement could not be previewed.')
    } finally {
      setUploading(false)
    }
  }

  return (
    <section id="imports" className="panel import-panel" aria-labelledby="import-heading">
      <div className="panel-heading">
        <div>
          <p className="eyebrow">Milestone 2</p>
          <h2 id="import-heading">Preview a statement</h2>
          <p className="panel-description">
            Upload a selectable-text Navy Federal checking PDF. Previewing does not create transactions.
          </p>
        </div>
      </div>

      <form className="import-form" onSubmit={submit}>
        <label>
          Checking account
          <select
            required
            value={accountId}
            disabled={loading || accounts.length === 0}
            onChange={(event) => setAccountId(event.target.value)}
          >
            {accounts.length === 0 && <option value="">No active checking accounts</option>}
            {accounts.map((account) => <option key={account.id} value={account.id}>{account.name}</option>)}
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
          </div>
          <pre>{preview.extracted_text}</pre>
          <p className="preview-note">Preview only — no transactions were created.</p>
        </div>
      )}
    </section>
  )
}
