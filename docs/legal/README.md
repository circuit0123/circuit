> **DRAFT — for lawyer review.**

# Legal drafts

Drafts for the lawyer (LAUNCH.md Stage 7 "[YOU] Lawyer review"). None of this is in force. They were written from what the product does today.

| File | What it is |
|---|---|
| `privacy-policy.md` | Privacy Policy, with every processor from PRODUCTION.md §5 and the data each receives |
| `terms.md` | Terms of Use |
| `cookie-notice.md` | Cookie and local-storage notice (check against the real frontend) |
| `refund-and-cancellation.md` | Refund and cancellation policy for promotions (needed before payments go live) |
| `community-guidelines.md` | Community guidelines |
| `grievance-officer.md` | Grievance Officer page |

**Placeholders to fill (never invented):** `<LEGAL_NAME>`, `<ADDRESS>`, `<GSTIN>`, `<GRIEVANCE_OFFICER>`, `<GRIEVANCE_EMAIL>`,
`<SUPPORT_EMAIL>`, `<LLM_PROVIDER>`, `<POLICY_VERSION>`, `<JURISDICTION>`, `<DATE>`, and the refund periods.

**How the text reaches members.** Each member accepts a **policy version**. The current version is the `POLICY_VERSION` setting. After the
lawyer's text is final, publish it and change `POLICY_VERSION` (for example `2026-02`): every member then sees the consent screen
and the API answers `403 consent_required` until they accept. No code change is needed. The grievance contact shown in the app comes from `GRIEVANCE_*` settings.

**Open questions for the lawyer** (also marked **[LAWYER]** in the files):
1. DPDP s.9: verifiable parental consent for under-18s. The product does not implement it. Admit only 18+ in the pilot, or build it?
2. Processor contracts and regions; whether any transfer outside India needs notice.
3. Retention of orders, payments and invoices (`FINANCIAL_RECORD_RETENTION_YEARS`, now 8): the accountant confirms the period.
4. Backups: deleted data stays in Supabase backups until they roll over. Is the stated backup period acceptable?
5. Posts, replies and messages stay as "Deleted member" after an account is deleted. Acceptable under the DPDP erasure right?
6. Intermediary safe-harbour wording and the grievance timelines (IT Rules 2021).
7. Right to nominate (DPDP s.14): what process do we offer?
8. Breach notice wording and who is notified.
9. Limitation of liability, indemnity, governing law and dispute resolution in the Terms.
