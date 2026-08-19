import { FormEvent, useEffect, useMemo, useState } from 'react'

import { Account, listAccounts } from '../../api/accounts'
import {
  AmortizationProjection,
  LoanBalance,
  LoanTerms,
  createLoan,
  createLoanBalance,
  deleteLoan,
  deleteLoanBalance,
  listLoanBalances,
  listLoans,
  projectAmortization,
  updateLoan,
  updateLoanBalance,
} from '../../api/debt'
import { onDataChanged } from '../../dataEvents'

const today = () => new Date().toISOString().slice(0, 10)
const money = (value: string) =>
  new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD' }).format(Number(value))

type TermsForm = {
  accountId: string
  principal: string
  rate: string
  payment: string
  term: string
}

const emptyTerms: TermsForm = { accountId: '', principal: '', rate: '', payment: '', term: '' }

export function DebtPlanner() {
  const [accounts, setAccounts] = useState<Account[]>([])
  const [loans, setLoans] = useState<LoanTerms[]>([])
  const [balances, setBalances] = useState<LoanBalance[]>([])
  const [selectedId, setSelectedId] = useState('')
  const [terms, setTerms] = useState<TermsForm>(emptyTerms)
  const [editingLoan, setEditingLoan] = useState<string | null>(null)
  const [balanceDate, setBalanceDate] = useState(today())
  const [balanceAmount, setBalanceAmount] = useState('')
  const [balanceSource, setBalanceSource] = useState('manual')
  const [editingBalance, setEditingBalance] = useState<string | null>(null)
  const [projectionPrincipal, setProjectionPrincipal] = useState('')
  const [projectionRate, setProjectionRate] = useState('')
  const [projectionPayment, setProjectionPayment] = useState('')
  const [firstPaymentDate, setFirstPaymentDate] = useState(today())
  const [projection, setProjection] = useState<AmortizationProjection | null>(null)
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const loanAccounts = useMemo(
    () => accounts.filter((account) => account.account_type === 'loan'),
    [accounts],
  )
  const accountMap = useMemo(
    () => new Map(accounts.map((account) => [account.id, account])),
    [accounts],
  )
  const selectedLoan = loans.find((loan) => loan.id === selectedId)

  async function loadCore() {
    const [accountResult, loanResult] = await Promise.all([listAccounts(), listLoans()])
    setAccounts(accountResult)
    setLoans(loanResult)
    setSelectedId((current) =>
      loanResult.some((loan) => loan.id === current) ? current : loanResult[0]?.id ?? '',
    )
  }

  useEffect(() => {
    let active = true
    Promise.all([listAccounts(), listLoans()])
      .then(([accountResult, loanResult]) => {
        if (!active) return
        setAccounts(accountResult)
        setLoans(loanResult)
        setSelectedId(loanResult[0]?.id ?? '')
      })
      .catch((reason: unknown) => {
        if (active) setError(reason instanceof Error ? reason.message : 'Debt data could not be loaded.')
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
    void loadCore().catch(() => setError('Debt accounts could not be refreshed.'))
  }), [])

  useEffect(() => {
    if (!selectedId) return
    let active = true
    listLoanBalances(selectedId)
      .then((result) => {
        if (active) setBalances(result)
      })
      .catch((reason: unknown) => {
        if (active) setError(reason instanceof Error ? reason.message : 'Balance history could not be loaded.')
      })
    return () => {
      active = false
    }
  }, [selectedId])

  function resetTerms() {
    setTerms({ ...emptyTerms, accountId: loanAccounts[0]?.id ?? '' })
    setEditingLoan(null)
  }

  async function submitTerms(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setSaving(true)
    setError(null)
    try {
      const payload = {
        account_id: terms.accountId,
        principal: terms.principal,
        annual_rate_basis_points: Number(terms.rate),
        minimum_payment: terms.payment,
        term_months: terms.term ? Number(terms.term) : null,
      }
      const saved = editingLoan
        ? await updateLoan(editingLoan, {
            principal: payload.principal,
            annual_rate_basis_points: payload.annual_rate_basis_points,
            minimum_payment: payload.minimum_payment,
            term_months: payload.term_months,
          })
        : await createLoan(payload)
      await loadCore()
      setSelectedId(saved.id)
      resetTerms()
    } catch (reason: unknown) {
      setError(reason instanceof Error ? reason.message : 'Loan terms could not be saved.')
    } finally {
      setSaving(false)
    }
  }

  function editTerms(loan: LoanTerms) {
    setEditingLoan(loan.id)
    setTerms({
      accountId: loan.account_id,
      principal: loan.principal,
      rate: String(loan.annual_rate_basis_points),
      payment: loan.minimum_payment,
      term: loan.term_months === null ? '' : String(loan.term_months),
    })
  }

  async function removeLoan(loan: LoanTerms) {
    try {
      await deleteLoan(loan.id)
      setBalances([])
      await loadCore()
      if (editingLoan === loan.id) resetTerms()
    } catch (reason: unknown) {
      setError(reason instanceof Error ? reason.message : 'Loan terms could not be deleted.')
    }
  }

  function resetBalance() {
    setEditingBalance(null)
    setBalanceDate(today())
    setBalanceAmount('')
    setBalanceSource('manual')
  }

  async function submitBalance(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (!selectedId) return
    setSaving(true)
    setError(null)
    const payload = { as_of_date: balanceDate, balance: balanceAmount, source: balanceSource }
    try {
      if (editingBalance) await updateLoanBalance(selectedId, editingBalance, payload)
      else await createLoanBalance(selectedId, payload)
      setBalances(await listLoanBalances(selectedId))
      resetBalance()
    } catch (reason: unknown) {
      setError(reason instanceof Error ? reason.message : 'Balance history could not be saved.')
    } finally {
      setSaving(false)
    }
  }

  async function removeBalance(balance: LoanBalance) {
    if (!selectedId) return
    try {
      await deleteLoanBalance(selectedId, balance.id)
      setBalances((current) => current.filter((item) => item.id !== balance.id))
      if (editingBalance === balance.id) resetBalance()
    } catch (reason: unknown) {
      setError(reason instanceof Error ? reason.message : 'Balance history could not be deleted.')
    }
  }

  function useSelectedLoan() {
    if (!selectedLoan) return
    setProjectionPrincipal(balances[0]?.balance ?? selectedLoan.principal)
    setProjectionRate(String(selectedLoan.annual_rate_basis_points))
    setProjectionPayment(selectedLoan.minimum_payment)
  }

  async function calculate(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setSaving(true)
    setError(null)
    setProjection(null)
    try {
      setProjection(await projectAmortization({
        principal: projectionPrincipal,
        annual_rate_basis_points: Number(projectionRate),
        monthly_payment: projectionPayment,
        first_payment_date: firstPaymentDate,
      }))
    } catch (reason: unknown) {
      setError(reason instanceof Error ? reason.message : 'The projection could not be calculated.')
    } finally {
      setSaving(false)
    }
  }

  return (
    <section id="debt" className="panel debt-panel" aria-labelledby="debt-heading">
      <div className="panel-heading category-heading">
        <div>
          <p className="eyebrow">Payoff planning</p>
          <h2 id="debt-heading">Debt planner</h2>
          <p className="panel-description">Record loan details and explore transparent payoff projections.</p>
        </div>
        <span className="category-count">{loans.length} debts</span>
      </div>

      {error && <p className="form-error" role="alert">{error}</p>}
      {loading ? <p className="empty-state">Loading debt plan…</p> : (
        <div className="debt-grid">
          <article>
            <h3>Loan terms</h3>
            <form className="debt-form" onSubmit={submitTerms}>
              <label>Loan account
                <select required disabled={Boolean(editingLoan)} value={terms.accountId} onChange={(event) => setTerms({ ...terms, accountId: event.target.value })}>
                  <option value="">Select an account</option>
                  {loanAccounts.map((account) => <option key={account.id} value={account.id}>{account.name}</option>)}
                </select>
              </label>
              <label>Original principal
                <input required min="0" step="0.01" type="number" value={terms.principal} onChange={(event) => setTerms({ ...terms, principal: event.target.value })} />
              </label>
              <label>APR in basis points
                <input required min="0" step="1" type="number" value={terms.rate} onChange={(event) => setTerms({ ...terms, rate: event.target.value })} />
                <small>100 basis points equals 1% APR.</small>
              </label>
              <label>Minimum monthly payment
                <input required min="0" step="0.01" type="number" value={terms.payment} onChange={(event) => setTerms({ ...terms, payment: event.target.value })} />
              </label>
              <label>Term in months <span className="optional-label">Optional</span>
                <input min="1" step="1" type="number" value={terms.term} onChange={(event) => setTerms({ ...terms, term: event.target.value })} />
              </label>
              <div className="form-actions">
                <button className="secondary-button" disabled={saving || !terms.accountId} type="submit">{editingLoan ? 'Save terms' : 'Add loan terms'}</button>
                {editingLoan && <button className="text-button" type="button" onClick={resetTerms}>Cancel</button>}
              </div>
            </form>
            {loanAccounts.length === 0 && <p className="form-hint">Create a loan account before adding terms.</p>}
            <ul className="debt-list">
              {loans.map((loan) => <li key={loan.id} className={loan.id === selectedId ? 'selected' : ''}>
                <button type="button" className="debt-select" onClick={() => setSelectedId(loan.id)}>
                  <strong>{accountMap.get(loan.account_id)?.name ?? 'Loan account'}</strong>
                  <span>{money(loan.principal)} · {(loan.annual_rate_basis_points / 100).toFixed(2)}% APR</span>
                </button>
                <button className="text-button" type="button" onClick={() => editTerms(loan)}>Edit</button>
                <button className="delete-button" type="button" onClick={() => removeLoan(loan)}>Delete</button>
              </li>)}
            </ul>
          </article>

          <article>
            <h3>Balance history</h3>
            {!selectedLoan ? <p className="empty-state">Select or add loan terms to record balances.</p> : <>
              <form className="debt-form compact" onSubmit={submitBalance}>
                <label>As of date<input required type="date" value={balanceDate} onChange={(event) => setBalanceDate(event.target.value)} /></label>
                <label>Balance<input required min="0" step="0.01" type="number" value={balanceAmount} onChange={(event) => setBalanceAmount(event.target.value)} /></label>
                <label>Source<input required maxLength={80} value={balanceSource} onChange={(event) => setBalanceSource(event.target.value)} /></label>
                <div className="form-actions">
                  <button className="secondary-button" disabled={saving} type="submit">{editingBalance ? 'Save balance' : 'Add balance'}</button>
                  {editingBalance && <button className="text-button" type="button" onClick={resetBalance}>Cancel</button>}
                </div>
              </form>
              {balances.length === 0 ? <p className="empty-state">No balance history yet. Projections can use the original principal.</p> : <ul className="debt-list balance-list">
                {balances.map((balance) => <li key={balance.id}>
                  <span><strong>{money(balance.balance)}</strong><small>{balance.as_of_date} · {balance.source}</small></span>
                  <button className="text-button" type="button" onClick={() => {
                    setEditingBalance(balance.id); setBalanceDate(balance.as_of_date); setBalanceAmount(balance.balance); setBalanceSource(balance.source)
                  }}>Edit</button>
                  <button className="delete-button" type="button" onClick={() => removeBalance(balance)}>Delete</button>
                </li>)}
              </ul>}
            </>}
          </article>
        </div>
      )}

      <article className="amortization-card">
        <div className="planning-section-heading">
          <div><h3>Amortization calculator</h3><p className="panel-description">This projection does not change saved loan data.</p></div>
          <button className="text-button" type="button" disabled={!selectedLoan} onClick={useSelectedLoan}>Use selected loan</button>
        </div>
        <form className="projection-form" onSubmit={calculate}>
          <label>Starting balance<input required min="0" step="0.01" type="number" value={projectionPrincipal} onChange={(event) => setProjectionPrincipal(event.target.value)} /></label>
          <label>APR in basis points<input required min="0" step="1" type="number" value={projectionRate} onChange={(event) => setProjectionRate(event.target.value)} /></label>
          <label>Monthly payment<input required min="0" step="0.01" type="number" value={projectionPayment} onChange={(event) => setProjectionPayment(event.target.value)} /></label>
          <label>First payment date<input required type="date" value={firstPaymentDate} onChange={(event) => setFirstPaymentDate(event.target.value)} /></label>
          <button className="primary-button" disabled={saving} type="submit">Calculate payoff</button>
        </form>

        {projection && <div className="projection-results" aria-live="polite">
          <dl className="projection-summary">
            <div><dt>Payoff date</dt><dd>{projection.payoff_date ?? 'Already paid'}</dd></div>
            <div><dt>Months</dt><dd>{projection.months}</dd></div>
            <div><dt>Total interest</dt><dd>{money(projection.total_interest)}</dd></div>
            <div><dt>Total paid</dt><dd>{money(projection.total_paid)}</dd></div>
          </dl>
          <details className="assumptions" open>
            <summary>Calculation assumptions</summary>
            <ul>
              <li>{projection.assumptions.apr_treatment}</li><li>{projection.assumptions.periodic_rate}</li>
              <li>{projection.assumptions.compounding}</li><li>{projection.assumptions.payment_timing}</li>
              <li>{projection.assumptions.currency_rounding}</li><li>{projection.assumptions.final_payment}</li>
            </ul>
            <p>{projection.assumptions.disclaimer}</p>
          </details>
          <div className="table-scroll" tabIndex={0} aria-label="Amortization schedule, horizontally scrollable">
            <table className="exact-table">
              <caption>Exact month-by-month amortization schedule</caption>
              <thead><tr><th scope="col">Month</th><th scope="col">Date</th><th scope="col">Starting balance</th><th scope="col">Interest</th><th scope="col">Principal</th><th scope="col">Payment</th><th scope="col">Ending balance</th></tr></thead>
              <tbody>{projection.payments.map((row) => <tr key={row.month}>
                <th scope="row">{row.month}</th><td>{row.payment_date}</td><td>{money(row.starting_balance)}</td><td>{money(row.interest)}</td><td>{money(row.principal)}</td><td>{money(row.payment)}</td><td>{money(row.ending_balance)}</td>
              </tr>)}</tbody>
            </table>
          </div>
        </div>}
      </article>
    </section>
  )
}
