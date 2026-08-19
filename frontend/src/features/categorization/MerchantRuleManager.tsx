import { FormEvent, useEffect, useMemo, useState } from 'react'

import { Category, listCategories } from '../../api/categories'
import {
  MerchantRule,
  MerchantRuleInput,
  RuleMatch,
  applyMerchantMatches,
  createMerchantRule,
  deleteMerchantRule,
  disableMerchantRule,
  listMerchantRules,
  previewMerchantMatches,
  updateMerchantRule,
} from '../../api/merchantRules'
import { emitDataChanged, onDataChanged } from '../../dataEvents'

const blank: MerchantRuleInput = {
  pattern: '', match_type: 'contains', category_id: '', priority: 100, enabled: true,
}

export function MerchantRuleManager() {
  const [rules, setRules] = useState<MerchantRule[]>([])
  const [categories, setCategories] = useState<Category[]>([])
  const [input, setInput] = useState(blank)
  const [editingId, setEditingId] = useState<string | null>(null)
  const [matches, setMatches] = useState<RuleMatch[] | null>(null)
  const [selected, setSelected] = useState<Set<string>>(new Set())
  const [unmatched, setUnmatched] = useState(0)
  const [busy, setBusy] = useState(false)
  const [message, setMessage] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const categoryNames = useMemo(() => new Map(categories.map((item) => [item.id, item.name])), [categories])

  useEffect(() => {
    Promise.all([listMerchantRules(), listCategories()])
      .then(([ruleResult, categoryResult]) => {
        setRules(ruleResult); setCategories(categoryResult)
        setInput((current) => ({ ...current, category_id: current.category_id || categoryResult[0]?.id || '' }))
      })
      .catch((reason: unknown) => setError(reason instanceof Error ? reason.message : 'Rules could not be loaded.'))
  }, [])

  useEffect(() => onDataChanged((scopes) => {
    if (!scopes.includes('categories')) return
    void listCategories()
      .then((result) => {
        setCategories(result)
        setInput((current) => ({
          ...current,
          category_id: result.some((category) => category.id === current.category_id)
            ? current.category_id
            : result[0]?.id ?? '',
        }))
      })
      .catch(() => setError('Categories could not be loaded.'))
  }), [])

  function reset(categoryId = categories[0]?.id || '') {
    setInput({ ...blank, category_id: categoryId }); setEditingId(null)
  }

  async function submit(event: FormEvent) {
    event.preventDefault(); setBusy(true); setError(null); setMessage(null)
    try {
      const saved = editingId
        ? await updateMerchantRule(editingId, input)
        : await createMerchantRule(input)
      setRules((current) => editingId
        ? current.map((rule) => rule.id === saved.id ? saved : rule)
        : [...current, saved].sort((a, b) => a.priority - b.priority))
      reset(saved.category_id); setMatches(null)
    } catch (reason) { setError(reason instanceof Error ? reason.message : 'Rule could not be saved.') }
    finally { setBusy(false) }
  }

  async function preview() {
    setBusy(true); setError(null); setMessage(null)
    try {
      const result = await previewMerchantMatches()
      setMatches(result.matches); setUnmatched(result.unmatched_count)
      setSelected(new Set(result.matches.map((match) => match.transaction_id)))
    } catch (reason) { setError(reason instanceof Error ? reason.message : 'Matches could not be previewed.') }
    finally { setBusy(false) }
  }

  async function apply() {
    setBusy(true); setError(null)
    try {
      const result = await applyMerchantMatches([...selected])
      setMessage(`Applied ${result.applied_count} categor${result.applied_count === 1 ? 'y' : 'ies'}${result.skipped_count ? `; skipped ${result.skipped_count} changed transaction(s)` : ''}.`)
      setMatches(null); setSelected(new Set())
      emitDataChanged('transactions', 'summary')
    } catch (reason) { setError(reason instanceof Error ? reason.message : 'Matches could not be applied.') }
    finally { setBusy(false) }
  }

  return <section id="merchant-rules" className="panel rule-panel" aria-labelledby="rule-heading">
    <div className="panel-heading"><div><p className="eyebrow">Explainable assistance</p><h2 id="rule-heading">Merchant rules</h2></div>
      <button className="secondary-button" type="button" disabled={busy || rules.length === 0} onClick={() => void preview()}>Preview matches</button></div>
    <p className="panel-description">Rules inspect a normalized copy of each merchant description. Nothing is categorized until you review and apply the preview.</p>
    {error && <p className="error-message" role="alert">{error}</p>}
    {message && <p className="success-message" role="status">{message}</p>}
    <div className="rule-layout">
      <form className="category-form" onSubmit={submit}>
        <h3>{editingId ? 'Edit rule' : 'Add a rule'}</h3>
        <label>Merchant pattern<input aria-label="Merchant pattern" required maxLength={200} value={input.pattern} onChange={(e) => setInput({ ...input, pattern: e.target.value })} /></label>
        <label>Match type<select aria-label="Match type" value={input.match_type} onChange={(e) => setInput({ ...input, match_type: e.target.value as MerchantRuleInput['match_type'] })}><option value="exact">Exact</option><option value="contains">Contains</option><option value="regex">Regular expression</option></select></label>
        <label>Category<select aria-label="Rule category" required value={input.category_id} onChange={(e) => setInput({ ...input, category_id: e.target.value })}><option value="" disabled>Select a category</option>{categories.map((category) => <option key={category.id} value={category.id}>{category.name}</option>)}</select></label>
        <label>Priority<input aria-label="Priority" type="number" min="0" max="10000" value={input.priority} onChange={(e) => setInput({ ...input, priority: Number(e.target.value) })} /></label>
        <div className="form-actions"><button className="primary-button" disabled={busy || !input.category_id}>{editingId ? 'Save rule' : 'Add rule'}</button>{editingId && <button type="button" className="text-button" onClick={() => reset()}>Cancel</button>}</div>
      </form>
      <div className="category-list"><h3>Rules</h3>{rules.length === 0 ? <p>No merchant rules yet.</p> : rules.map((rule) => <article className={`category-row${rule.enabled ? '' : ' archived'}`} key={rule.id}>
        <div><strong>{rule.pattern}</strong><small>{rule.match_type} · priority {rule.priority} · {categoryNames.get(rule.category_id) ?? 'Unavailable category'}{rule.enabled ? '' : ' · disabled'}</small></div>
        <div className="row-actions"><button className="text-button" onClick={() => { setEditingId(rule.id); setInput({ pattern: rule.pattern, match_type: rule.match_type, category_id: rule.category_id, priority: rule.priority, enabled: rule.enabled }) }}>Edit</button>{rule.enabled && <button className="text-button" onClick={() => void disableMerchantRule(rule.id).then((saved) => setRules((current) => current.map((item) => item.id === saved.id ? saved : item))).catch((reason: unknown) => setError(reason instanceof Error ? reason.message : 'Rule could not be disabled.'))}>Disable</button>}<button className="text-button danger" onClick={() => { if (window.confirm('Delete this merchant rule?')) void deleteMerchantRule(rule.id).then(() => setRules((current) => current.filter((item) => item.id !== rule.id))).catch((reason: unknown) => setError(reason instanceof Error ? reason.message : 'Rule could not be deleted.')) }}>Delete</button></div>
      </article>)}</div>
    </div>
    {matches && <div className="match-review"><h3>Match review</h3><p>{matches.length} matched · {unmatched} unmatched. Existing categories are excluded.</p>{matches.length === 0 ? <p>No uncategorized transactions match enabled rules.</p> : <><div className="match-list">{matches.map((match) => <label className="match-row" key={match.transaction_id}><input type="checkbox" aria-label={`Apply ${match.description}`} checked={selected.has(match.transaction_id)} onChange={(e) => { const next = new Set(selected); if (e.target.checked) next.add(match.transaction_id); else next.delete(match.transaction_id); setSelected(next) }} /><span><strong>{match.description}</strong><small>{match.posted_date} · {match.amount} → {match.category_name} via “{match.rule_pattern}”{match.competing_rule_ids.length ? ` · ${match.competing_rule_ids.length} lower-precedence match(es)` : ''}</small></span></label>)}</div><button className="primary-button" disabled={busy || selected.size === 0} onClick={() => void apply()}>Apply {selected.size} selected</button></>}</div>}
  </section>
}
