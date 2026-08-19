import { FormEvent, useEffect, useState } from 'react'

import {
  Account,
  AccountInput,
  AccountType,
  archiveAccount,
  createAccount,
  listAccounts,
  updateAccount,
} from '../../api/accounts'
import { emitDataChanged } from '../../dataEvents'

const initialInput: AccountInput = {
  name: '',
  institution: '',
  account_type: 'checking',
  currency: 'USD',
  current_balance: null,
}

function displayType(accountType: AccountType) {
  return accountType.replace('_', ' ')
}

function displayBalance(account: Account) {
  if (account.current_balance === null) return 'Balance not set'
  try {
    return new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency: account.currency,
    }).format(Number(account.current_balance))
  } catch {
    return `${account.currency} ${account.current_balance}`
  }
}

export function AccountManager() {
  const [accounts, setAccounts] = useState<Account[]>([])
  const [input, setInput] = useState<AccountInput>(initialInput)
  const [balance, setBalance] = useState('')
  const [editingId, setEditingId] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let active = true
    listAccounts()
      .then((result) => {
        if (active) setAccounts(result)
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

  function resetForm() {
    setInput(initialInput)
    setBalance('')
    setEditingId(null)
  }

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setSaving(true)
    setError(null)
    const payload = { ...input, current_balance: balance === '' ? null : balance }
    try {
      const saved = editingId
        ? await updateAccount(editingId, payload)
        : await createAccount(payload)
      setAccounts((current) =>
        [...current.filter((account) => account.id !== saved.id), saved].sort((left, right) =>
          left.name.localeCompare(right.name),
        ),
      )
      resetForm()
      emitDataChanged('accounts')
    } catch (reason: unknown) {
      setError(reason instanceof Error ? reason.message : 'The account could not be saved.')
    } finally {
      setSaving(false)
    }
  }

  function beginEditing(account: Account) {
    setEditingId(account.id)
    setInput({
      name: account.name,
      institution: account.institution,
      account_type: account.account_type,
      currency: account.currency,
      current_balance: account.current_balance,
    })
    setBalance(account.current_balance ?? '')
    setError(null)
  }

  async function archive(account: Account) {
    setError(null)
    try {
      await archiveAccount(account.id)
      setAccounts((current) => current.filter((item) => item.id !== account.id))
      if (editingId === account.id) resetForm()
      emitDataChanged('accounts')
    } catch (reason: unknown) {
      setError(reason instanceof Error ? reason.message : 'The account could not be archived.')
    }
  }

  return (
    <section id="accounts" className="panel account-panel" aria-labelledby="account-heading">
      <div className="panel-heading category-heading">
        <div>
          <p className="eyebrow">Financial sources</p>
          <h2 id="account-heading">Accounts</h2>
        </div>
        <span className="category-count">{accounts.length} active</span>
      </div>

      <div className="category-layout">
        <form className="category-form" onSubmit={submit}>
          <h3>{editingId ? 'Edit account' : 'Add an account'}</h3>
          <label>
            Name
            <input
              required
              maxLength={120}
              value={input.name}
              onChange={(event) => setInput({ ...input, name: event.target.value })}
              placeholder="e.g. Primary checking"
            />
          </label>
          <label>
            Institution
            <input
              required
              maxLength={120}
              value={input.institution}
              onChange={(event) => setInput({ ...input, institution: event.target.value })}
              placeholder="e.g. Navy Federal"
            />
          </label>
          <div className="account-form-row">
            <label>
              Type
              <select
                value={input.account_type}
                onChange={(event) =>
                  setInput({ ...input, account_type: event.target.value as AccountType })
                }
              >
                <option value="checking">Checking</option>
                <option value="credit_card">Credit card</option>
              </select>
            </label>
            <label>
              Currency
              <input
                required
                minLength={3}
                maxLength={3}
                value={input.currency}
                onChange={(event) => setInput({ ...input, currency: event.target.value.toUpperCase() })}
              />
            </label>
          </div>
          <label>
            Current balance <span className="optional-label">Optional</span>
            <input
              type="number"
              step="0.01"
              value={balance}
              onChange={(event) => setBalance(event.target.value)}
              placeholder="0.00"
            />
          </label>
          <div className="form-actions">
            <button className="primary-button" type="submit" disabled={saving}>
              {saving ? 'Saving…' : editingId ? 'Save changes' : 'Add account'}
            </button>
            {editingId && (
              <button className="text-button" type="button" onClick={resetForm}>
                Cancel
              </button>
            )}
          </div>
        </form>

        <div className="category-list-wrap" aria-live="polite">
          {error && <p className="form-error" role="alert">{error}</p>}
          {loading ? (
            <p className="empty-state">Loading accounts…</p>
          ) : accounts.length === 0 ? (
            <p className="empty-state">No accounts yet. Add one before recording transactions.</p>
          ) : (
            <ul className="category-list account-list">
              {accounts.map((account) => (
                <li key={account.id}>
                  <span className="account-mark" aria-hidden="true">▤</span>
                  <span className="category-details">
                    <strong>{account.name}</strong>
                    <span>{account.institution} · {displayType(account.account_type)}</span>
                  </span>
                  <strong className="account-balance">{displayBalance(account)}</strong>
                  <button className="text-button" type="button" onClick={() => beginEditing(account)}>
                    Edit
                  </button>
                  <button className="archive-button" type="button" onClick={() => archive(account)}>
                    Archive
                  </button>
                </li>
              ))}
            </ul>
          )}
        </div>
      </div>
    </section>
  )
}
