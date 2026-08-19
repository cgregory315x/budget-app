import { useCallback, useEffect, useMemo, useState } from 'react'

import { MonthlySummary, getMonthlySummary } from '../../api/monthlySummary'
import { onDataChanged } from '../../dataEvents'

function currentMonth() {
  const current = new Date()
  const offset = current.getTimezoneOffset() * 60_000
  return new Date(current.getTime() - offset).toISOString().slice(0, 7)
}

const currency = new Intl.NumberFormat('en-US', {
  style: 'currency',
  currency: 'USD',
  maximumFractionDigits: 2,
})

function money(value: string) {
  return currency.format(Number(value))
}

function monthName(value: string) {
  const [year, month] = value.split('-').map(Number)
  return new Intl.DateTimeFormat('en-US', { month: 'long', year: 'numeric' }).format(
    new Date(year, month - 1, 1),
  )
}

export function MonthlySummaryDashboard() {
  const [month, setMonth] = useState(currentMonth())
  const [summary, setSummary] = useState<MonthlySummary | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const loadSummary = useCallback(async (selectedMonth: string) => {
    setError(null)
    setSummary(await getMonthlySummary(selectedMonth))
  }, [])

  useEffect(() => {
    let active = true
    getMonthlySummary(month)
      .then((result) => {
        if (active) setSummary(result)
      })
      .catch((reason: unknown) => {
        if (active) setError(reason instanceof Error ? reason.message : 'Summary unavailable.')
      })
      .finally(() => {
        if (active) setLoading(false)
      })
    return () => {
      active = false
    }
  }, [month])

  useEffect(() => onDataChanged((scopes) => {
    if (!scopes.includes('summary')) return
    setLoading(true)
    void loadSummary(month)
      .catch((reason: unknown) => {
        setError(reason instanceof Error ? reason.message : 'Summary unavailable.')
      })
      .finally(() => setLoading(false))
  }), [loadSummary, month])

  const compositionBackground = useMemo(() => {
    if (!summary || Number(summary.total_spending) <= 0) return '#edeae2'
    let position = 0
    const stops = summary.category_spending.map((category) => {
      const start = position
      position += (Number(category.spent) / Number(summary.total_spending)) * 100
      return `${category.color} ${start}% ${position}%`
    })
    return `conic-gradient(${stops.join(', ')})`
  }, [summary])

  if (loading) {
    return <section id="overview" className="panel summary-state">Loading monthly summary…</section>
  }
  if (error || !summary) {
    return <section id="overview" className="form-error summary-state" role="alert">{error ?? 'Summary unavailable.'}</section>
  }

  return (
    <section id="overview" className="summary-dashboard" aria-label="Monthly summary">
      <div className="summary-toolbar">
        <div>
          <p className="eyebrow">{monthName(month)}</p>
          <h2>Monthly overview</h2>
        </div>
        <label className="month-picker">
          Month
          <input
            type="month"
            value={month}
            onChange={(event) => {
              setLoading(true)
              setError(null)
              setMonth(event.target.value)
            }}
          />
        </label>
      </div>

      <div className="summary-grid">
        <article className="summary-card featured">
          <p>Available after spending</p>
          <strong>{money(summary.available_after_spending)}</strong>
          <span>
            {summary.remaining_percent === null
              ? 'Add expected income to calculate a percentage'
              : `${summary.remaining_percent}% of income remains`}
          </span>
        </article>
        <article className="summary-card">
          <p>Expected income</p>
          <strong>{money(summary.planned_income)}</strong>
          <span className="positive">{money(summary.actual_inflows)} in recorded inflows</span>
        </article>
        <article className="summary-card">
          <p>Total spending</p>
          <strong>{money(summary.total_spending)}</strong>
          <span>
            {summary.spending_percent === null
              ? 'No expected income set'
              : `${summary.spending_percent}% of expected income`}
          </span>
        </article>
        <article className="summary-card">
          <p>Needs review</p>
          <strong>{summary.uncategorized_count}</strong>
          <span className={summary.uncategorized_count ? 'attention' : 'positive'}>
            Uncategorized transactions
          </span>
        </article>
      </div>

      <div className="dashboard-grid real-dashboard-grid">
        <article className="panel budget-panel">
          <div className="panel-heading">
            <div>
              <p className="eyebrow">Category limits</p>
              <h2>Budget progress</h2>
            </div>
          </div>
          {summary.budget_progress.length === 0 ? (
            <p className="empty-state dashboard-empty">No category budgets set for this month.</p>
          ) : (
            <div className="progress-list">
              {summary.budget_progress.map((budget) => {
                const width = Math.min(Number(budget.percent_used ?? 0), 100)
                return (
                  <div className="progress-item" key={budget.budget_id}>
                    <div className="progress-label">
                      <span>{budget.name}</span>
                      <span
                        className={budget.overspent ? 'attention' : ''}
                        aria-label={`${money(budget.spent)} spent of ${money(budget.limit_amount)}`}
                      >
                        <strong>{money(budget.spent)}</strong> / {money(budget.limit_amount)}
                      </span>
                    </div>
                    <div className="progress-track">
                      <span
                        className="progress-fill"
                        style={{
                          width: `${width}%`,
                          backgroundColor: budget.overspent ? '#D56F62' : budget.color,
                        }}
                      />
                    </div>
                  </div>
                )
              })}
            </div>
          )}
        </article>

        <article className="panel composition-panel">
          <div className="panel-heading">
            <div>
              <p className="eyebrow">Where it went</p>
              <h2>Spending mix</h2>
            </div>
          </div>
          <div className="donut-wrap">
            <div
              className="donut"
              style={{ background: compositionBackground }}
              role="img"
              aria-label={`Spending composition totaling ${money(summary.total_spending)}`}
            >
              <div>
                <strong>{money(summary.total_spending)}</strong>
                <span>Total</span>
              </div>
            </div>
          </div>
          {summary.category_spending.length === 0 ? (
            <p className="sample-note">No spending recorded for this month.</p>
          ) : (
            <ul className="composition-legend">
              {summary.category_spending.map((category) => (
                <li key={category.category_id ?? 'uncategorized'}>
                  <i style={{ backgroundColor: category.color }} />
                  <span>{category.name}</span>
                  <strong>{money(category.spent)}</strong>
                </li>
              ))}
            </ul>
          )}
        </article>
      </div>
    </section>
  )
}
