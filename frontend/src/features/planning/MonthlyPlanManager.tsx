import { FormEvent, useEffect, useMemo, useState } from 'react'

import { Category, listCategories } from '../../api/categories'
import {
  MonthlyBudget,
  MonthlyIncome,
  createBudget,
  createIncome,
  deleteBudget,
  deleteIncome,
  listBudgets,
  listIncome,
  updateBudget,
  updateIncome,
} from '../../api/monthlyPlanning'

function currentMonth() {
  const current = new Date()
  const offset = current.getTimezoneOffset() * 60_000
  return new Date(current.getTime() - offset).toISOString().slice(0, 7)
}

function money(value: string) {
  return new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD' }).format(Number(value))
}

export function MonthlyPlanManager() {
  const [month, setMonth] = useState(currentMonth())
  const [categories, setCategories] = useState<Category[]>([])
  const [budgets, setBudgets] = useState<MonthlyBudget[]>([])
  const [income, setIncome] = useState<MonthlyIncome[]>([])
  const [budgetCategory, setBudgetCategory] = useState('')
  const [budgetLimit, setBudgetLimit] = useState('')
  const [incomeDescription, setIncomeDescription] = useState('')
  const [incomeAmount, setIncomeAmount] = useState('')
  const [editingBudget, setEditingBudget] = useState<string | null>(null)
  const [editingIncome, setEditingIncome] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const expenseCategories = useMemo(
    () => categories.filter((category) => category.kind === 'expense'),
    [categories],
  )
  const categoryMap = useMemo(
    () => new Map(categories.map((category) => [category.id, category])),
    [categories],
  )

  async function load(selectedMonth: string) {
    setLoading(true)
    setError(null)
    try {
      const [budgetResult, incomeResult] = await Promise.all([
        listBudgets(selectedMonth),
        listIncome(selectedMonth),
      ])
      setBudgets(budgetResult)
      setIncome(incomeResult)
    } catch (reason: unknown) {
      setError(reason instanceof Error ? reason.message : 'The monthly plan could not be loaded.')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    let active = true
    Promise.all([listCategories(), listBudgets(month), listIncome(month)])
      .then(([categoryResult, budgetResult, incomeResult]) => {
        if (!active) return
        setCategories(categoryResult)
        setBudgets(budgetResult)
        setIncome(incomeResult)
        setBudgetCategory(categoryResult.find((category) => category.kind === 'expense')?.id ?? '')
      })
      .catch((reason: unknown) => {
        if (active) setError(reason instanceof Error ? reason.message : 'The monthly plan could not be loaded.')
      })
      .finally(() => {
        if (active) setLoading(false)
      })
    return () => {
      active = false
    }
  }, [month])

  function resetBudgetForm() {
    setEditingBudget(null)
    setBudgetCategory(expenseCategories[0]?.id ?? '')
    setBudgetLimit('')
  }

  function resetIncomeForm() {
    setEditingIncome(null)
    setIncomeDescription('')
    setIncomeAmount('')
  }

  async function submitBudget(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setSaving(true)
    setError(null)
    const input = { month: `${month}-01`, category_id: budgetCategory, limit_amount: budgetLimit }
    try {
      if (editingBudget) await updateBudget(editingBudget, input)
      else await createBudget(input)
      resetBudgetForm()
      await load(month)
    } catch (reason: unknown) {
      setError(reason instanceof Error ? reason.message : 'The budget could not be saved.')
    } finally {
      setSaving(false)
    }
  }

  async function submitIncome(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setSaving(true)
    setError(null)
    const input = { month: `${month}-01`, description: incomeDescription, amount: incomeAmount }
    try {
      if (editingIncome) await updateIncome(editingIncome, input)
      else await createIncome(input)
      resetIncomeForm()
      await load(month)
    } catch (reason: unknown) {
      setError(reason instanceof Error ? reason.message : 'The income entry could not be saved.')
    } finally {
      setSaving(false)
    }
  }

  async function removeBudget(entry: MonthlyBudget) {
    setError(null)
    try {
      await deleteBudget(entry.id)
      if (editingBudget === entry.id) resetBudgetForm()
      await load(month)
    } catch (reason: unknown) {
      setError(reason instanceof Error ? reason.message : 'The budget could not be deleted.')
    }
  }

  async function removeIncome(entry: MonthlyIncome) {
    setError(null)
    try {
      await deleteIncome(entry.id)
      if (editingIncome === entry.id) resetIncomeForm()
      await load(month)
    } catch (reason: unknown) {
      setError(reason instanceof Error ? reason.message : 'The income entry could not be deleted.')
    }
  }

  return (
    <section id="budgets" className="panel planning-panel" aria-labelledby="planning-heading">
      <div className="panel-heading category-heading">
        <div>
          <p className="eyebrow">Monthly plan</p>
          <h2 id="planning-heading">Budgets and income</h2>
        </div>
        <label className="month-picker">
          Month
          <input
            type="month"
            value={month}
            onChange={(event) => {
              setMonth(event.target.value)
              resetBudgetForm()
              resetIncomeForm()
            }}
          />
        </label>
      </div>

      {error && <p className="form-error planning-error" role="alert">{error}</p>}
      {loading ? (
        <p className="empty-state planning-loading">Loading monthly plan…</p>
      ) : (
        <div className="planning-grid">
          <article>
            <div className="planning-section-heading">
              <h3>Category budgets</h3>
              <strong>{money(budgets.reduce((sum, item) => sum + Number(item.limit_amount), 0).toFixed(2))}</strong>
            </div>
            <form className="planning-form" onSubmit={submitBudget}>
              <select
                aria-label="Budget category"
                required
                value={budgetCategory}
                onChange={(event) => setBudgetCategory(event.target.value)}
              >
                <option value="" disabled>Select an expense category</option>
                {expenseCategories.map((category) => <option key={category.id} value={category.id}>{category.name}</option>)}
              </select>
              <input
                aria-label="Budget limit"
                required
                min="0"
                step="0.01"
                type="number"
                value={budgetLimit}
                onChange={(event) => setBudgetLimit(event.target.value)}
                placeholder="Limit"
              />
              <button className="secondary-button" type="submit" disabled={saving || !budgetCategory}>
                {editingBudget ? 'Save' : 'Add'}
              </button>
              {editingBudget && <button className="text-button" type="button" onClick={resetBudgetForm}>Cancel</button>}
            </form>
            {expenseCategories.length === 0 && <p className="form-hint">Add an expense category before setting a budget.</p>}
            <ul className="planning-list">
              {budgets.map((budget) => {
                const category = categoryMap.get(budget.category_id)
                return (
                  <li key={budget.id}>
                    <i style={{ backgroundColor: category?.color ?? '#667085' }} />
                    <strong>{category?.name ?? 'Archived category'}</strong>
                    <span>{money(budget.limit_amount)}</span>
                    <button className="text-button" type="button" onClick={() => {
                      setEditingBudget(budget.id)
                      setBudgetCategory(budget.category_id)
                      setBudgetLimit(budget.limit_amount)
                    }}>Edit</button>
                    <button className="delete-button" type="button" onClick={() => removeBudget(budget)}>Delete</button>
                  </li>
                )
              })}
            </ul>
          </article>

          <article>
            <div className="planning-section-heading">
              <h3>Expected income</h3>
              <strong>{money(income.reduce((sum, item) => sum + Number(item.amount), 0).toFixed(2))}</strong>
            </div>
            <form className="planning-form" onSubmit={submitIncome}>
              <input
                aria-label="Income description"
                required
                maxLength={160}
                value={incomeDescription}
                onChange={(event) => setIncomeDescription(event.target.value)}
                placeholder="Description"
              />
              <input
                aria-label="Income amount"
                required
                min="0.01"
                step="0.01"
                type="number"
                value={incomeAmount}
                onChange={(event) => setIncomeAmount(event.target.value)}
                placeholder="Amount"
              />
              <button className="secondary-button" type="submit" disabled={saving}>
                {editingIncome ? 'Save' : 'Add'}
              </button>
              {editingIncome && <button className="text-button" type="button" onClick={resetIncomeForm}>Cancel</button>}
            </form>
            <ul className="planning-list income-list">
              {income.map((entry) => (
                <li key={entry.id}>
                  <strong>{entry.description}</strong>
                  <span>{money(entry.amount)}</span>
                  <button className="text-button" type="button" onClick={() => {
                    setEditingIncome(entry.id)
                    setIncomeDescription(entry.description)
                    setIncomeAmount(entry.amount)
                  }}>Edit</button>
                  <button className="delete-button" type="button" onClick={() => removeIncome(entry)}>Delete</button>
                </li>
              ))}
            </ul>
          </article>
        </div>
      )}
    </section>
  )
}
