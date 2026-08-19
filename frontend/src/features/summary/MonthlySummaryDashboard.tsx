import { useCallback, useEffect, useMemo, useState } from 'react'

import {
  MonthlySummary,
  MonthlyTrends,
  getMonthlySummary,
  getMonthlyTrends,
} from '../../api/monthlySummary'
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

function shortMonthName(value: string) {
  const [year, month] = value.slice(0, 7).split('-').map(Number)
  return new Intl.DateTimeFormat('en-US', { month: 'short' }).format(
    new Date(year, month - 1, 1),
  )
}

export function MonthlySummaryDashboard() {
  const [month, setMonth] = useState(currentMonth())
  const [summary, setSummary] = useState<MonthlySummary | null>(null)
  const [trends, setTrends] = useState<MonthlyTrends | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const loadReporting = useCallback(async (selectedMonth: string) => {
    setError(null)
    const [nextSummary, nextTrends] = await Promise.all([
      getMonthlySummary(selectedMonth),
      getMonthlyTrends(selectedMonth),
    ])
    setSummary(nextSummary)
    setTrends(nextTrends)
  }, [])

  useEffect(() => {
    let active = true
    Promise.all([getMonthlySummary(month), getMonthlyTrends(month)])
      .then(([nextSummary, nextTrends]) => {
        if (active) {
          setSummary(nextSummary)
          setTrends(nextTrends)
        }
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
    void loadReporting(month)
      .catch((reason: unknown) => {
        setError(reason instanceof Error ? reason.message : 'Summary unavailable.')
      })
      .finally(() => setLoading(false))
  }), [loadReporting, month])

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

  const trendMaximum = useMemo(() => Math.max(
    1,
    ...(trends?.months.flatMap((point) => [
      Number(point.actual_inflows),
      Number(point.total_spending),
    ]) ?? []),
  ), [trends])

  if (loading) {
    return <section id="overview" className="panel summary-state">Loading monthly summary…</section>
  }
  if (error || !summary || !trends) {
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
                const percentUsed = Number(budget.percent_used ?? 0)
                const width = Math.min(percentUsed, 100)
                const statusText = budget.overspent
                  ? `Over budget by ${money(String(Math.abs(Number(budget.remaining))))}`
                  : `${money(budget.remaining)} remaining`
                const percentageText = budget.percent_used === null
                  ? 'Percentage unavailable for a zero-dollar limit'
                  : `${budget.percent_used}% used`
                return (
                  <div
                    className={`progress-item${budget.overspent ? ' is-overspent' : ''}`}
                    key={budget.budget_id}
                  >
                    <div className="progress-label">
                      <span>{budget.name}</span>
                      <span
                        className={budget.overspent ? 'attention' : ''}
                        aria-label={`${money(budget.spent)} spent of ${money(budget.limit_amount)}`}
                      >
                        <strong>{money(budget.spent)}</strong> / {money(budget.limit_amount)}
                      </span>
                    </div>
                    <div
                      className="progress-track"
                      role="progressbar"
                      aria-label={`${budget.name} budget usage`}
                      aria-valuemin={0}
                      aria-valuemax={100}
                      aria-valuenow={Math.min(percentUsed, 100)}
                      aria-valuetext={`${statusText}; ${percentageText}`}
                    >
                      <span
                        className="progress-fill"
                        style={{
                          width: `${width}%`,
                          backgroundColor: budget.overspent ? '#D56F62' : budget.color,
                        }}
                      />
                    </div>
                    <p className={`budget-status${budget.overspent ? ' attention' : ''}`}>
                      <strong>{statusText}</strong>
                      <span>{percentageText}</span>
                    </p>
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


      <article className="panel trend-panel" aria-labelledby="trend-title">
        <div className="panel-heading trend-heading">
          <div>
            <p className="eyebrow">Six-month view</p>
            <h2 id="trend-title">Income versus spending</h2>
          </div>
          <ul className="trend-legend" aria-label="Chart legend">
            <li><i className="income-key" />Recorded income</li>
            <li><i className="spending-key" />Spending</li>
          </ul>
        </div>
        <figure className="trend-figure">
          <div className="trend-chart" aria-hidden="true">
            {trends.months.map((point) => (
              <div className="trend-month" key={point.month}>
                <div className="trend-bars">
                  <i
                    className="trend-bar income-bar"
                    style={{ height: `${(Number(point.actual_inflows) / trendMaximum) * 100}%` }}
                  />
                  <i
                    className="trend-bar spending-bar"
                    style={{ height: `${(Number(point.total_spending) / trendMaximum) * 100}%` }}
                  />
                </div>
                <span>{shortMonthName(point.month)}</span>
              </div>
            ))}
          </div>
          <figcaption>Recorded income and budget-counted spending by month.</figcaption>
        </figure>
        <div className="trend-table-wrap">
          <table className="trend-table">
            <caption>Exact monthly trend values</caption>
            <thead>
              <tr>
                <th scope="col">Month</th>
                <th scope="col">Expected income</th>
                <th scope="col">Recorded income</th>
                <th scope="col">Spending</th>
              </tr>
            </thead>
            <tbody>
              {trends.months.map((point) => (
                <tr key={point.month}>
                  <th scope="row">{monthName(point.month.slice(0, 7))}</th>
                  <td>{money(point.planned_income)}</td>
                  <td>{money(point.actual_inflows)}</td>
                  <td>{money(point.total_spending)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </article>
    </section>
  )
}
