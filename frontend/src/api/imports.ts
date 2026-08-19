export type StatementImportPreview = {
  account_id: string
  adapter: string
  statement: {
    filename: string
    content_type: string
    size_bytes: number
    page_count: number
    text_character_count: number
    file_sha256: string
    duplicate: {
      is_duplicate: boolean
      existing_import_id: string | null
    }
  }
  parsed_statement: {
    institution: string
    account_hint: string | null
    period_start: string | null
    period_end: string | null
    warnings: string[]
    transactions: CandidateTransactionPreview[]
  }
  extracted_text: string
}

export type CandidateTransactionPreview = {
  posted_date: string
  description: string
  amount: string
  source_text: string
  confidence: string
  warnings: string[]
  duplicate_status: 'exact' | 'possible' | null
  matched_transaction_id: string | null
}

type ApiErrorBody = { detail?: string }

export type StatementImportConfirmInput = {
  account_id: string
  adapter: string
  file_sha256: string
  statement_start: string | null
  statement_end: string | null
  warnings: string[]
  candidates: Array<{
    posted_date: string
    description: string
    amount: string
    confidence: string | null
    allow_duplicate: boolean
  }>
}

export type StatementImportConfirmResponse = {
  import_id: string
  transaction_ids: string[]
  transaction_count: number
}

async function responseJson<T>(response: Response, fallback: string): Promise<T> {
  if (!response.ok) {
    let message = fallback
    try {
      const error = (await response.json()) as ApiErrorBody
      if (typeof error.detail === 'string') message = error.detail
    } catch {
      // Preserve a stable message for non-JSON proxy or server responses.
    }
    throw new Error(message)
  }
  return (await response.json()) as T
}

export async function previewStatement(accountId: string, file: File): Promise<StatementImportPreview> {
  const body = new FormData()
  body.append('account_id', accountId)
  body.append('file', file)

  const response = await fetch('/api/v1/imports/preview', { method: 'POST', body })
  return responseJson<StatementImportPreview>(response, 'The statement could not be previewed.')
}

export async function confirmStatementImport(
  input: StatementImportConfirmInput,
): Promise<StatementImportConfirmResponse> {
  const response = await fetch('/api/v1/imports/confirm', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(input),
  })
  return responseJson<StatementImportConfirmResponse>(response, 'The statement could not be imported.')
}
