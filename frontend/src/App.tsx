import { useEffect, useState } from 'react'

import { AccountManager } from './features/accounts/AccountManager'
import { CategoryManager } from './features/categories/CategoryManager'
import { MonthlyPlanManager } from './features/planning/MonthlyPlanManager'
import { TransactionManager } from './features/transactions/TransactionManager'

type ApiState = 'checking' | 'online' | 'offline'

const currency = new Intl.NumberFormat('en-US', {
  style: 'currency',
  currency: 'USD',
  maximumFractionDigits: 0,
})

function App() {
  const [apiState, setApiState] = useState<ApiState>('checking')

  useEffect(() => {
    const controller = new AbortController()

    fetch('/api/v1/health', { signal: controller.signal })
      .then((response) => {
        if (!response.ok) throw new Error('API health check failed')
        setApiState('online')
      })
      .catch((error: unknown) => {
        if (error instanceof DOMException && error.name === 'AbortError') return
        setApiState('offline')
      })

    return () => controller.abort()
  }, [])

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <a className="brand" href="#top" aria-label="Budget App home">
          <span className="brand-mark">B</span>
          <span>Budget App</span>
        </a>

        <nav className="nav-list" aria-label="Primary navigation">
          <a className="nav-item active" href="#overview">
            <span aria-hidden="true">◫</span> Overview
          </a>
          <a className="nav-item" href="#transactions">
            <span aria-hidden="true">↔</span> Transactions
          </a>
          <a className="nav-item" href="#budgets">
            <span aria-hidden="true">◎</span> Budgets
          </a>
          <a className="nav-item" href="#categories">
            <span aria-hidden="true">◇</span> Categories
          </a>
          <a className="nav-item" href="#accounts">
            <span aria-hidden="true">▤</span> Accounts
          </a>
          <a className="nav-item" href="#debt">
            <span aria-hidden="true">⌁</span> Debt plan
          </a>
        </nav>

        <div className="sidebar-footer">
          <span className={`status-dot ${apiState}`} aria-hidden="true" />
          <span>
            API {apiState === 'checking' ? 'checking' : apiState}
          </span>
        </div>
      </aside>

      <main id="top" className="main-content">
        <header className="page-header">
          <div>
            <p className="eyebrow">August 2026</p>
            <h1>Your monthly picture</h1>
            <p className="subtitle">Track what came in, what went out, and what needs attention.</p>
          </div>
          <button className="primary-button" type="button">
            <span aria-hidden="true">↑</span> Import statement
          </button>
        </header>

        <section id="overview" className="summary-grid" aria-label="Monthly summary">
          <article className="summary-card featured">
            <p>Available after spending</p>
            <strong>{currency.format(1916)}</strong>
            <span>31% of income remains</span>
          </article>
          <article className="summary-card">
            <p>Monthly income</p>
            <strong>{currency.format(6250)}</strong>
            <span className="positive">On plan</span>
          </article>
          <article className="summary-card">
            <p>Total spending</p>
            <strong>{currency.format(4334)}</strong>
            <span>69% of income</span>
          </article>
          <article className="summary-card">
            <p>Needs review</p>
            <strong>7</strong>
            <span className="attention">Uncategorized transactions</span>
          </article>
        </section>

        <section className="dashboard-grid">
          <article className="panel composition-panel">
            <div className="panel-heading">
              <div>
                <p className="eyebrow">Where it went</p>
                <h2>Spending mix</h2>
              </div>
            </div>
            <div className="donut-wrap">
              <div className="donut" role="img" aria-label="Sample category spending composition">
                <div>
                  <strong>{currency.format(4334)}</strong>
                  <span>Total</span>
                </div>
              </div>
            </div>
            <p className="sample-note">Sample data · Connect the API to replace</p>
          </article>

        </section>

        <MonthlyPlanManager />
        <TransactionManager />
        <AccountManager />
        <CategoryManager />
      </main>
    </div>
  )
}

export default App
