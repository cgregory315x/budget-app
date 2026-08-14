export type CategoryKind = 'expense' | 'income' | 'transfer'

export type Category = {
  id: string
  name: string
  kind: CategoryKind
  color: string
  archived: boolean
  created_at: string
  updated_at: string
}

export type CategoryInput = {
  name: string
  kind: CategoryKind
  color: string
}

type ApiErrorBody = { detail?: string }

async function request<T>(url: string, init?: RequestInit): Promise<T> {
  const response = await fetch(url, init)
  if (!response.ok) {
    let message = 'The category request failed.'
    try {
      const body = (await response.json()) as ApiErrorBody
      if (typeof body.detail === 'string') message = body.detail
    } catch {
      // Keep the generic message when an intermediary returns a non-JSON response.
    }
    throw new Error(message)
  }
  if (response.status === 204) return undefined as T
  return (await response.json()) as T
}

export function listCategories(): Promise<Category[]> {
  return request<Category[]>('/api/v1/categories')
}

export function createCategory(input: CategoryInput): Promise<Category> {
  return request<Category>('/api/v1/categories', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(input),
  })
}

export function updateCategory(id: string, input: CategoryInput): Promise<Category> {
  return request<Category>(`/api/v1/categories/${id}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(input),
  })
}

export function archiveCategory(id: string): Promise<void> {
  return request<void>(`/api/v1/categories/${id}`, { method: 'DELETE' })
}
