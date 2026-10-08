# Comparing pending dividends with issuer records

`scripts/triage_two_year_dividends.py` checks every event in the 143-row
pending queue against the saved Massive event and the dated security map. It
then looks for a separate issuer record in
`reference/dividend_issuer_evidence.csv`. The reference file contains 12
manually checked rows from Chevron, PepsiCo and UnitedHealth issuer pages.
The source URL and check date are saved with each row.

Run:

```powershell
.\.venv\dbt\Scripts\python.exe scripts\triage_two_year_dividends.py
```

The output is `data/two_year_action_triage/v1/triage.csv`; its manifest records
hashes of the queue, provider file, issuer reference and security map. The
script can be rerun against the same inputs. To change evidence later, use a
new output version instead of overwriting this review result.

Current result:

| Result | Events | Meaning |
| --- | ---: | --- |
| `PARTIAL_ISSUER_MATCH` | 10 | Issuer and provider agree on the issuer-published fields. The issuer page does not establish the ex-date. |
| `ISSUER_CONFLICT` | 2 | Both Chevron records have a different declared date from the issuer history. Their ex-dates are also unverified by that page. |
| `NO_ISSUER_EVIDENCE` | 131 | This first reference batch has no matching issuer row. This is not proof of an error. |

The 12 compared events represent $49,038.6425 of the queue's $161,806.8125
gross absolute review exposure. Exposure adds the absolute amounts from both
accounts; it is not a current NAV balance or a cash amount received.

No row is automatically approved. An issuer match checks some **event facts**,
but the accounting decision also needs a supported ex-date, the correct
security, the account's opening shares, and payment evidence before cash is
marked paid. In particular, the issuer pages used here show record and payment
dates but no ex-date. A dated price row or a second copy of the Massive record
does not independently establish that missing fact.

The [first twelve review packet](action_reviews/top_twelve_2026-10-06.md)
adds US exchange rules, three notices from other trading venues, account
exposure and the two recorded Chevron holds. It still makes no new approval.

The first Chevron event remains on hold in
`docs/action_reviews/cvx_2026-05-19.json`. The second Chevron conflict also
has a HOLD decision. This triage report itself changes no approval or NAV.
One PepsiCo event was subsequently approved in
`docs/action_reviews/decision_ledger_003.json`; 142 events remain pending in
that provisional close.
