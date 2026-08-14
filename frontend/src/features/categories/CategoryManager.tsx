import { FormEvent, useEffect, useState } from 'react'

import {
  archiveCategory,
  Category,
  CategoryInput,
  CategoryKind,
  createCategory,
  listCategories,
  updateCategory,
} from '../../api/categories'

const initialInput: CategoryInput = {
  name: '',
  kind: 'expense',
  color: '#397D72',
}

export function CategoryManager() {
  const [categories, setCategories] = useState<Category[]>([])
  const [input, setInput] = useState<CategoryInput>(initialInput)
  const [editingId, setEditingId] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let active = true
    listCategories()
      .then((result) => {
        if (active) setCategories(result)
      })
      .catch((reason: unknown) => {
        if (active) setError(reason instanceof Error ? reason.message : 'Categories could not be loaded.')
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
    setEditingId(null)
  }

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setSaving(true)
    setError(null)
    try {
      const saved = editingId
        ? await updateCategory(editingId, input)
        : await createCategory(input)
      setCategories((current) =>
        [...current.filter((category) => category.id !== saved.id), saved].sort((left, right) =>
          left.name.localeCompare(right.name),
        ),
      )
      resetForm()
    } catch (reason: unknown) {
      setError(reason instanceof Error ? reason.message : 'The category could not be saved.')
    } finally {
      setSaving(false)
    }
  }

  function beginEditing(category: Category) {
    setEditingId(category.id)
    setInput({ name: category.name, kind: category.kind, color: category.color })
    setError(null)
  }

  async function archive(category: Category) {
    setError(null)
    try {
      await archiveCategory(category.id)
      setCategories((current) => current.filter((item) => item.id !== category.id))
      if (editingId === category.id) resetForm()
    } catch (reason: unknown) {
      setError(reason instanceof Error ? reason.message : 'The category could not be archived.')
    }
  }

  return (
    <section id="categories" className="panel category-panel" aria-labelledby="category-heading">
      <div className="panel-heading category-heading">
        <div>
          <p className="eyebrow">Budget building blocks</p>
          <h2 id="category-heading">Categories</h2>
        </div>
        <span className="category-count">{categories.length} active</span>
      </div>

      <div className="category-layout">
        <form className="category-form" onSubmit={submit}>
          <h3>{editingId ? 'Edit category' : 'Add a category'}</h3>
          <label>
            Name
            <input
              required
              maxLength={80}
              value={input.name}
              onChange={(event) => setInput({ ...input, name: event.target.value })}
              placeholder="e.g. Groceries"
            />
          </label>
          <label>
            Type
            <select
              value={input.kind}
              onChange={(event) =>
                setInput({ ...input, kind: event.target.value as CategoryKind })
              }
            >
              <option value="expense">Expense</option>
              <option value="income">Income</option>
              <option value="transfer">Transfer</option>
            </select>
          </label>
          <label>
            Color
            <span className="color-field">
              <input
                aria-label="Category color"
                type="color"
                value={input.color}
                onChange={(event) => setInput({ ...input, color: event.target.value.toUpperCase() })}
              />
              <span>{input.color}</span>
            </span>
          </label>
          <div className="form-actions">
            <button className="primary-button" type="submit" disabled={saving}>
              {saving ? 'Saving…' : editingId ? 'Save changes' : 'Add category'}
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
            <p className="empty-state">Loading categories…</p>
          ) : categories.length === 0 ? (
            <p className="empty-state">No categories yet. Add one to start organizing your budget.</p>
          ) : (
            <ul className="category-list">
              {categories.map((category) => (
                <li key={category.id}>
                  <span className="category-swatch" style={{ backgroundColor: category.color }} />
                  <span className="category-details">
                    <strong>{category.name}</strong>
                    <span>{category.kind}</span>
                  </span>
                  <button className="text-button" type="button" onClick={() => beginEditing(category)}>
                    Edit
                  </button>
                  <button className="archive-button" type="button" onClick={() => archive(category)}>
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
