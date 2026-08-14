import { FormEvent, useCallback, useEffect, useMemo, useState } from 'react'

import { Account, listAccounts } from '../../api/accounts'
import { Category, listCategories } from '../../api/categories'
import {
  Transaction,
  TransactionFilters,
  TransactionInput,
  createTransaction,
  deleteTransaction,
  listTransactions,
  updateTransaction,
} from '../../api/transactions'

function today() {
  const current = new Date()
  const offset = current.getTimezoneOffset() * 60_000
  return new Date(current.getTime() - offset).toISOString().slice(0, 10)
}

const initialInput: TransactionInput = {
  account_id: '',
  category_id: null,
  posted_date: today(),
  description: '',
  amount: '',
  excluded_from_budget: false,
}

type FilterState = {
  account: string
  category: string
  posted_from: string
  posted_to: string
  search: string
}

const initialFilters: FilterState = {
  account: '',
  category: '',
  posted_from: '',
  posted_to: '',
  search: '',
}

export function TransactionManager() {
  const [transactions, setTransactions] = useState<Transaction[]>([])
  const [accounts, setAccounts] = useState<Account[]>([])
  const [categories, setCategories] = useState<Category[]>([])
  const [input, setInput] = useState<TransactionInput>(initialInput)
  const [filters, setFilters] = useState<FilterState>(initialFilters)
  const [editingId, setEditingId] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const accountNames = useMemo(
    () => new Map(accounts.map((account) => [account.id, account.name])),
    [accounts],
  )
  const categoryDetails = useMemo(
    () => new Map(categories.map((category) => [category.id, category])),
    [categories],
  )

  const loadTransactions = useCallback(async (nextFilters: FilterState) => {
    const requestFilters: TransactionFilters = {
      account_id: nextFilters.account || undefined,
      posted_from: nextFilters.posted_from || undefined,
      posted_to: nextFilters.posted_to || undefined,
      search: nextFilters.search.trim() || undefined,
    }
    if (nextFilters.category === 'uncategorized') requestFilters.uncategorized = true
    else if (nextFilters.category) requestFilters.category_id = nextFilters.category
    return listTransactions(requestFilters)
  }, [])

  useEffect(() => {
    let active = true
    Promise.all([listAccounts(), listCategories(), loadTransactions(initialFilters)])
      .then(([accountResult, categoryResult, transactionResult]) => {
        if (!active) return
        setAccounts(accountResult)
        setCategories(categoryResult)
        setTransactions(transactionResult)
        setInput((current) => ({
          ...current,
          account_id: current.account_id || accountResult[0]?.id || '',
        }))
      })
      .catch((reason: unknown) => {
        if (active) setError(reason instanceof Error ? reason.message : 'Transactions could not be loaded.')
      })
      .finally(() => {
        if (active) setLoading(false)
      })
    return () => {
      active = false
    }
  }, [loadTransactions])

  function resetForm() {
    setInput({ ...initialInput, account_id: accounts[0]?.id || '' })
    setEditingId(null)
  }

  async function refresh(nextFilters = filters) {
    setLoading(true)
    setError(null)
    try {
      setTransactions(await loadTransactions(nextFilters))
    } catch (reason: unknown) {
      setError(reason instanceof Error ? reason.message : 'Transactions could not be loaded.')
    } finally {
      setLoading(false)
    }
  }

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setSaving(true)
    setError(null)
    try {
      if (editingId) await updateTransaction(editingId, input)
      else await createTransaction(input)
      resetForm()
      await refresh()
    } catch (reason: unknown) {
      setError(reason instanceof Error ? reason.message : 'The transaction could not be saved.')
    } finally {
      setSaving(false)
    }
  }

  function beginEditing(transaction: Transaction) {
    setEditingId(transaction.id)
    setInput({
      account_id: transaction.account_id,
      category_id: transaction.category_id,
      posted_date: transaction.posted_date,
      description: transaction.description,
      amount: transaction.amount,
      excluded_from_budget: transaction.excluded_from_budget,
    })
    setError(null)
  }

  async function remove(transaction: Transaction) {
    if (!window.confirm('Delete this transaction? This cannot be undone.')) return
    setError(null)
    try {
      await deleteTransaction(transaction.id)
      if (editingId === transaction.id) resetForm()
      await refresh()
    } catch (reason: unknown) {
      setError(reason instanceof Error ? reason.message : 'The transaction could not be deleted.')
    }
  }

  function formatAmount(transaction: Transaction) {
    const account = accounts.find((item) => item.id === transaction.account_id)
    try {
      return new Intl.NumberFormat('en-US', {
        style: 'currency',
        currency: account?.currency ?? 'USD',
      }).format(Number(transaction.amount))
    } catch {
      return transaction.amount
    }
  }

  return (
    <section id="transactions" className="panel transaction-panel" aria-labelledby="transaction-heading">
      <div className="panel-heading category-heading">
        <div>
          <p className="eyebrow">Manual ledger</p>
          <h2 id="transaction-heading">Transactions</h2>
        </div>
        <span className="category-count">{transactions.length} shown</span>
      </div>

      <form className="transaction-filters" onSubmit={(event) => { event.preventDefault(); void refresh() }}>
        <input
          aria-label="Search descriptions"
          value={filters.search}
          onChange={(event) => setFilters({ ...filters, search: event.target.value })}
          placeholder="Search descriptions"
        />
        <select
          aria-label="Filter by account"
          value={filters.account}
          onChange={(event) => setFilters({ ...filters, account: event.target.value })}
        >
          <option value="">All accounts</option>
          {accounts.map((account) => <option key={account.id} value={account.id}>{account.name}</option>)}
        </select>
        <select
          aria-label="Filter by category"
          value={filters.category}
          onChange={(event) => setFilters({ ...filters, category: event.target.value })}
        >
          <option value="">All categories</option>
          <option value="uncategorized">Uncategorized</option>
          {categories.map((category) => <option key={category.id} value={category.id}>{category.name}</option>)}
        </select>
        <input
          aria-label="Posted from"
          type="date"
          value={filters.posted_from}
          onChange={(event) => setFilters({ ...filters, posted_from: event.target.value })}
        />
        <input
          aria-label="Posted to"
          type="date"
          value={filters.posted_to}
          onChange={(event) => setFilters({ ...filters, posted_to: event.target.value })}
        />
        <button className="secondary-button" type="submit">Apply filters</button>
        <button
          className="text-button"
          type="button"
          onClick={() => { setFilters(initialFilters); void refresh(initialFilters) }}
        >
          Clear
        </button>
      </form>

      <div className="transaction-layout">
        <form className="category-form transaction-form" onSubmit={submit}>
          <h3>{editingId ? 'Edit transaction' : 'Add a transaction'}</h3>
          {accounts.length === 0 && <p className="form-hint">Add an account before recording a transaction.</p>}
          <label>
            Account
            <select
              required
              value={input.account_id}
              onChange={(event) => setInput({ ...input, account_id: event.target.value })}
            >
              <option value="" disabled>Select an account</option>
              {accounts.map((account) => <option key={account.id} value={account.id}>{account.name}</option>)}
            </select>
          </label>
          <label>
            Date
            <input
              required
              type="date"
              value={input.posted_date}
              onChange={(event) => setInput({ ...input, posted_date: event.target.value })}
            />
          </label>
          <label>
            Description
            <input
              required
              maxLength={500}
              value={input.description}
              onChange={(event) => setInput({ ...input, description: event.target.value })}
              placeholder="e.g. Example Market"
            />
          </label>
          <label>
            Amount
            <input
              required
              type="number"
              step="0.01"
              value={input.amount}
              onChange={(event) => setInput({ ...input, amount: event.target.value })}
              placeholder="Use a negative amount for spending"
            />
          </label>
          <label>
            Category <span className="optional-label">Optional</span>
            <select
              value={input.category_id ?? ''}
              onChange={(event) => setInput({ ...input, category_id: event.target.value || null })}
            >
              <option value="">Uncategorized</option>
              {categories.map((category) => <option key={category.id} value={category.id}>{category.name}</option>)}
            </select>
          </label>
          <label className="checkbox-label">
            <input
              type="checkbox"
              checked={input.excluded_from_budget}
              onChange={(event) => setInput({ ...input, excluded_from_budget: event.target.checked })}
            />
            Exclude from budget totals
          </label>
          <div className="form-actions">
            <button className="primary-button" type="submit" disabled={saving || accounts.length === 0}>
              {saving ? 'Saving…' : editingId ? 'Save changes' : 'Add transaction'}
            </button>
            {editingId && <button className="text-button" type="button" onClick={resetForm}>Cancel</button>}
          </div>
        </form>

        <div className="transaction-list-wrap" aria-live="polite">
          {error && <p className="form-error" role="alert">{error}</p>}
          {loading ? (
            <p className="empty-state">Loading transactions…</p>
          ) : transactions.length === 0 ? (
            <p className="empty-state">No transactions match the current filters.</p>
          ) : (
            <ul className="transaction-list">
              {transactions.map((transaction) => {
                const category = transaction.category_id
                  ? categoryDetails.get(transaction.category_id)
                  : undefined
                return (
                  <li key={transaction.id}>
                    <span className="transaction-date">{transaction.posted_date}</span>
                    <span className="transaction-description">
                      <strong>{transaction.description}</strong>
                      <span>{accountNames.get(transaction.account_id) ?? 'Unknown account'}</span>
                    </span>
                    <span className="transaction-category">
                      {category && <i style={{ backgroundColor: category.color }} />}
                      {category?.name ?? 'Uncategorized'}
                    </span>
                    <strong className={Number(transaction.amount) < 0 ? 'amount-out' : 'amount-in'}>
                      {formatAmount(transaction)}
                    </strong>
                    <button className="text-button" type="button" onClick={() => beginEditing(transaction)}>Edit</button>
                    <button className="delete-button" type="button" onClick={() => remove(transaction)}>Delete</button>
                    {transaction.excluded_from_budget && <span className="excluded-badge">Excluded</span>}
                  </li>
                )
              })}
            </ul>
          )}
        </div>
      </div>
    </section>
  )
}
