import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { MerchantRuleManager } from './MerchantRuleManager'

const category = { id: 'cat-1', name: 'Groceries', kind: 'expense', color: '#123456', archived: false, created_at: '', updated_at: '' }
const rule = { id: 'rule-1', pattern: 'Acme', pattern_normalized: 'ACME', match_type: 'contains', category_id: 'cat-1', priority: 100, enabled: true }
const match = { transaction_id: 'tx-1', description: 'Acme #42', merchant_normalized: 'ACME 42', posted_date: '2026-08-01', amount: '-12.50', rule_id: 'rule-1', rule_pattern: 'Acme', category_id: 'cat-1', category_name: 'Groceries', competing_rule_ids: [] }

function json(body: unknown, status = 200) { return new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } }) }

describe('MerchantRuleManager', () => {
  afterEach(() => { cleanup(); vi.unstubAllGlobals() })

  it('creates a deterministic rule', async () => {
    const fetchMock = vi.fn().mockResolvedValueOnce(json([])).mockResolvedValueOnce(json([category])).mockResolvedValueOnce(json(rule, 201))
    vi.stubGlobal('fetch', fetchMock); render(<MerchantRuleManager />)
    await screen.findByText('No merchant rules yet.')
    fireEvent.change(screen.getByLabelText('Merchant pattern'), { target: { value: 'Acme' } })
    fireEvent.click(screen.getByRole('button', { name: 'Add rule' }))
    expect(await screen.findByText('Acme')).toBeInTheDocument()
    expect(fetchMock).toHaveBeenLastCalledWith('/api/v1/merchant-rules', expect.objectContaining({ method: 'POST' }))
  })

  it('refreshes the dropdown after categories change', async () => {
    const fetchMock = vi.fn()
      .mockResolvedValueOnce(json([]))
      .mockResolvedValueOnce(json([]))
      .mockResolvedValueOnce(json([category]))
    vi.stubGlobal('fetch', fetchMock)
    render(<MerchantRuleManager />)

    await screen.findByText('No merchant rules yet.')
    expect(screen.queryByRole('option', { name: 'Groceries' })).not.toBeInTheDocument()

    window.dispatchEvent(new CustomEvent('budget-app:data-changed', {
      detail: ['categories'],
    }))

    expect(await screen.findByRole('option', { name: 'Groceries' })).toBeInTheDocument()
    expect(screen.getByLabelText('Rule category')).toHaveValue(category.id)
  })

  it('corrects a preview, learns an exact rule, and explicitly applies it', async () => {
    const coffee = { ...category, id: 'cat-2', name: 'Coffee' }
    const learnedRule = { ...rule, id: 'rule-2', pattern: 'ACME 42', match_type: 'exact', category_id: coffee.id }
    const fetchMock = vi.fn().mockResolvedValueOnce(json([rule])).mockResolvedValueOnce(json([category, coffee])).mockResolvedValueOnce(json({ matches: [match], unmatched_count: 2 })).mockResolvedValueOnce(json({ applied_count: 1, skipped_count: 0, learned_rule_count: 1 })).mockResolvedValueOnce(json([rule, learnedRule]))
    vi.stubGlobal('fetch', fetchMock); render(<MerchantRuleManager />)
    await screen.findByText('Acme')
    fireEvent.click(screen.getByRole('button', { name: 'Preview matches' }))
    expect(await screen.findByText(/2 unmatched/)).toBeInTheDocument()
    fireEvent.change(screen.getByLabelText('Category for Acme #42'), { target: { value: coffee.id } })
    fireEvent.click(screen.getByLabelText('Save exact rule for Acme #42'))
    fireEvent.click(screen.getByRole('button', { name: 'Apply 1 selected' }))
    expect(await screen.findByRole('status')).toHaveTextContent('Applied 1 category')
    expect(screen.getByRole('status')).toHaveTextContent('saved 1 exact rule')
    await waitFor(() => expect(fetchMock).toHaveBeenCalledWith(
      '/api/v1/merchant-rules/matches/apply',
      expect.objectContaining({
        method: 'POST',
        body: JSON.stringify({ decisions: [{ transaction_id: match.transaction_id, category_id: coffee.id, save_exact_rule: true }] }),
      }),
    ))
  })
})
