export type StatementImportPreview = {
  account_id: string
  adapter: string
  statement: {
    filename: string
    content_type: string
    size_bytes: number
    page_count: number
    text_character_count: number
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
}

type ApiErrorBody = { detail?: string }

export async function previewStatement(accountId: string, file: File): Promise<StatementImportPreview> {
  const body = new FormData()
  body.append('account_id', accountId)
  body.append('file', file)

  const response = await fetch('/api/v1/imports/preview', { method: 'POST', body })
  if (!response.ok) {
    let message = 'The statement could not be previewed.'
    try {
      const error = (await response.json()) as ApiErrorBody
      if (typeof error.detail === 'string') message = error.detail
    } catch {
      // Preserve a stable message for non-JSON proxy or server responses.
    }
    throw new Error(message)
  }
  return (await response.json()) as StatementImportPreview
}
