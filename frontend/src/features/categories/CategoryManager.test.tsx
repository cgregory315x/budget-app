import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { CategoryManager } from './CategoryManager'

const category = {
  id: 'eef5b14c-7d2d-44b1-87c2-efdf16ce144b',
  name: 'Synthetic Groceries',
  kind: 'expense',
  color: '#397D72',
  archived: false,
  created_at: '2026-08-14T12:00:00Z',
  updated_at: '2026-08-14T12:00:00Z',
}

const archivedCategory = { ...category, archived: true }

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
  })
}

describe('CategoryManager', () => {
  afterEach(() => {
    cleanup()
    vi.unstubAllGlobals()
  })

  it('shows the empty state after loading', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(jsonResponse([])))
    render(<CategoryManager />)

    expect(screen.getByText('Loading categories…')).toBeInTheDocument()
    expect(await screen.findByText(/No categories yet/)).toBeInTheDocument()
  })

  it('creates and displays a category', async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(jsonResponse([]))
      .mockResolvedValueOnce(jsonResponse(category, 201))
    vi.stubGlobal('fetch', fetchMock)
    render(<CategoryManager />)

    await screen.findByText(/No categories yet/)
    fireEvent.change(screen.getByLabelText('Name'), {
      target: { value: 'Synthetic Groceries' },
    })
    fireEvent.click(screen.getByRole('button', { name: 'Add category' }))

    expect(await screen.findByText('Synthetic Groceries')).toBeInTheDocument()
    expect(fetchMock).toHaveBeenLastCalledWith(
      '/api/v1/categories',
      expect.objectContaining({ method: 'POST' }),
    )
  })

  it('archives a category from the active list', async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(jsonResponse([category]))
      .mockResolvedValueOnce(new Response(null, { status: 204 }))
    vi.stubGlobal('fetch', fetchMock)
    render(<CategoryManager />)

    await screen.findByText('Synthetic Groceries')
    fireEvent.click(screen.getByRole('button', { name: 'Archive' }))

    await waitFor(() => expect(screen.queryByText('Synthetic Groceries')).not.toBeInTheDocument())
    expect(screen.getByText(/No active categories/)).toBeInTheDocument()
  })

  it('surfaces a sanitized API error', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(jsonResponse({ detail: 'Category service unavailable' }, 503)),
    )
    render(<CategoryManager />)

    expect(await screen.findByRole('alert')).toHaveTextContent('Category service unavailable')
  })

  it('shows and restores archived categories', async () => {
    const fetchMock = vi.fn()
      .mockResolvedValueOnce(jsonResponse([archivedCategory]))
      .mockResolvedValueOnce(jsonResponse(category))
    vi.stubGlobal('fetch', fetchMock)
    render(<CategoryManager />)

    await screen.findByText(/No active categories/)
    fireEvent.click(screen.getByLabelText('Show archived (1)'))
    expect(await screen.findByText('Synthetic Groceries')).toBeInTheDocument()
    expect(screen.getByText('expense · archived')).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'Restore' }))

    expect(await screen.findByRole('button', { name: 'Archive' })).toBeInTheDocument()
    expect(fetchMock).toHaveBeenLastCalledWith(
      `/api/v1/categories/${category.id}/restore`,
      { method: 'POST' },
    )
  })
})
