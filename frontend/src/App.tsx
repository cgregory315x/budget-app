import { useEffect, useState } from 'react'

import { AccountManager } from './features/accounts/AccountManager'
import { CategoryManager } from './features/categories/CategoryManager'
import { MerchantRuleManager } from './features/categorization/MerchantRuleManager'
import { StatementImportPanel } from './features/imports/StatementImportPanel'
import { MonthlyPlanManager } from './features/planning/MonthlyPlanManager'
import { MonthlySummaryDashboard } from './features/summary/MonthlySummaryDashboard'
import { TransactionManager } from './features/transactions/TransactionManager'

type ApiState = 'checking' | 'online' | 'offline'

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
          <a className="nav-item" href="#merchant-rules">
            <span aria-hidden="true">✦</span> Merchant rules
          </a>
          <a className="nav-item" href="#accounts">
            <span aria-hidden="true">▤</span> Accounts
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
            <p className="eyebrow">Live budget data</p>
            <h1>Your monthly picture</h1>
            <p className="subtitle">Track what came in, what went out, and what needs attention.</p>
          </div>
          <a className="primary-button" href="#imports">
            <span aria-hidden="true">↑</span> Import statement
          </a>
        </header>

        <StatementImportPanel />
        <MonthlySummaryDashboard />

        <MonthlyPlanManager />
        <TransactionManager />
        <MerchantRuleManager />
        <AccountManager />
        <CategoryManager />
      </main>
    </div>
  )
}

export default App
