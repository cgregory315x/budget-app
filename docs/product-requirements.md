# Product Requirements

## Product statement

Budget App helps one person turn financial statements into an accurate monthly view of spending, category budgets, income, and eventually debt-payoff options. It prioritizes user review over opaque automation.

## Initial user

- One local user.
- Web-first experience with a path to a mobile client later.
- Local development and use first; hosting is undecided.
- The product should be polished enough to demonstrate in a software portfolio.

## Core workflow

1. The user uploads a selectable-text Navy Federal checking statement PDF.
2. The app extracts candidate transactions into a temporary import.
3. The app flags low-confidence or incomplete rows.
4. The user reviews and corrects the import.
5. Confirmed transactions are saved and the original PDF is deleted.
6. Deterministic merchant rules propose categories for matching transactions.
7. The user previews, approves, excludes, or corrects each proposed category.
8. Corrections may become reusable exact merchant rules.
9. The dashboard updates monthly spending, income, and budget progress.

## MVP capabilities

### Accounts and transactions

- Create checking, credit-card, and loan accounts.
- Import Navy Federal checking transactions from a statement PDF.
- Add, edit, split, and delete transactions manually.
- Detect likely duplicate imports and transactions.
- Preserve the original transaction description alongside a separate normalized merchant value.

### Categorization

- Maintain user-defined spending categories.
- Propose categories through deterministic, explainable merchant rules.
- Require explicit user approval before a rule match changes a transaction.
- Learn deterministic merchant rules from accepted or corrected categorizations.
- Allow rules to be reviewed, edited, disabled, and deleted.

### Monthly budgeting

- Record monthly expected income.
- Assign category spending limits by month.
- Compare actual category spending with its limit.
- Show total spending as a proportion of income.
- Support uncategorized and excluded transactions.

### Visual reporting

- Monthly spending summary.
- Category budget progress.
- Spending composition by category.
- Income versus spending.
- Clear warnings for overspent categories and uncategorized transactions.

## Later milestones

- Additional credit-card and institution statement adapters beyond Navy Federal.
- Loan payment and balance history.
- Interest and payoff projections.
- Snowball, avalanche, and custom debt-payoff scenarios.
- Bank synchronization.
- Authentication, encryption/key management, and hosted deployment.
- Responsive mobile experience or native mobile client.

## Privacy and safety requirements

- Do not retain a successfully imported PDF.
- Use temporary files with bounded lifetime and cleanup after failure or cancellation.
- Keep statement text, transaction descriptions, and account metadata inside the application.
- Never log raw PDF content or secrets.
- Make uncertain parsing visible; do not silently infer financial amounts.

## MVP non-goals

- Supporting every institution immediately.
- Fully autonomous categorization.
- External categorization or machine-learning providers.
- Direct movement of money.
- Financial, tax, or investment advice.
- Multi-user households.
- Production hosting and bank synchronization.

## Success criteria

- A supported Navy Federal statement imports without manual re-entry of every row.
- Every extracted row is reviewable before persistence.
- Previously learned merchant rules are applied consistently.
- The user can understand monthly spending against category limits and income at a glance.
- Reimporting the same statement produces a duplicate warning rather than duplicate data.
