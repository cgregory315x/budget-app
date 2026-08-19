import { FormEvent, useEffect, useState } from 'react'

import {
  archiveCategory,
  Category,
  CategoryInput,
  CategoryKind,
  createCategory,
  listCategories,
  restoreCategory,
  updateCategory,
} from '../../api/categories'
import { emitDataChanged } from '../../dataEvents'

const initialInput: CategoryInput = {
  name: '',
  kind: 'expense',
  color: '#397D72',
}

export function CategoryManager() {
  const [categories, setCategories] = useState<Category[]>([])
  const [input, setInput] = useState<CategoryInput>(initialInput)
  const [editingId, setEditingId] = useState<string | null>(null)
  const [showArchived, setShowArchived] = useState(false)
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let active = true
    listCategories(true)
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
      emitDataChanged('categories')
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
      setCategories((current) => current.map((item) =>
        item.id === category.id ? { ...item, archived: true } : item,
      ))
      if (editingId === category.id) resetForm()
      emitDataChanged('categories')
    } catch (reason: unknown) {
      setError(reason instanceof Error ? reason.message : 'The category could not be archived.')
    }
  }

  async function restore(category: Category) {
    setError(null)
    try {
      const restored = await restoreCategory(category.id)
      setCategories((current) => current.map((item) =>
        item.id === restored.id ? restored : item,
      ))
      emitDataChanged('categories')
    } catch (reason: unknown) {
      setError(reason instanceof Error ? reason.message : 'The category could not be restored.')
    }
  }

  const activeCategories = categories.filter((category) => !category.archived)
  const visibleCategories = showArchived
    ? categories
    : activeCategories

  return (
    <section id="categories" className="panel category-panel" aria-labelledby="category-heading">
      <div className="panel-heading category-heading">
        <div>
          <p className="eyebrow">Budget building blocks</p>
          <h2 id="category-heading">Categories</h2>
        </div>
        <div className="category-heading-actions">
          <label className="show-archived-label">
            <input
              type="checkbox"
              checked={showArchived}
              onChange={(event) => setShowArchived(event.target.checked)}
            />
            Show archived ({categories.length - activeCategories.length})
          </label>
          <span className="category-count">{activeCategories.length} active</span>
        </div>
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
          ) : visibleCategories.length === 0 ? (
            <p className="empty-state">
              {categories.length > 0
                ? 'No active categories. Turn on Show archived to restore one.'
                : 'No categories yet. Add one to start organizing your budget.'}
            </p>
          ) : (
            <ul className="category-list">
              {visibleCategories.map((category) => (
                <li key={category.id} className={category.archived ? 'archived-row' : ''}>
                  <span className="category-swatch" style={{ backgroundColor: category.color }} />
                  <span className="category-details">
                    <strong>{category.name}</strong>
                    <span>{category.kind}{category.archived ? ' · archived' : ''}</span>
                  </span>
                  {category.archived ? (
                    <button className="text-button" type="button" onClick={() => restore(category)}>
                      Restore
                    </button>
                  ) : (
                    <>
                      <button className="text-button" type="button" onClick={() => beginEditing(category)}>
                        Edit
                      </button>
                      <button className="archive-button" type="button" onClick={() => archive(category)}>
                        Archive
                      </button>
                    </>
                  )}
                </li>
              ))}
            </ul>
          )}
        </div>
      </div>
    </section>
  )
}
