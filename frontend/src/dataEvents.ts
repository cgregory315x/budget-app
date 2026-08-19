export type BudgetDataScope = 'accounts' | 'transactions' | 'summary'

const eventName = 'budget-app:data-changed'

export function emitDataChanged(...scopes: BudgetDataScope[]) {
  window.dispatchEvent(new CustomEvent<BudgetDataScope[]>(eventName, { detail: scopes }))
}

export function onDataChanged(
  listener: (scopes: BudgetDataScope[]) => void,
): () => void {
  const handler = (event: Event) => {
    listener((event as CustomEvent<BudgetDataScope[]>).detail)
  }
  window.addEventListener(eventName, handler)
  return () => window.removeEventListener(eventName, handler)
}
