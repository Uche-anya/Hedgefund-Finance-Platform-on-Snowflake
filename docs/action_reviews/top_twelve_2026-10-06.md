# First twelve dividend reviews

These are the twelve highest-exposure events in the two-year pending queue.
Run `scripts/prepare_top_dividend_reviews.py` to recreate
`data/two_year_action_review/top12_evidence_v1/review.csv`. The adjacent
manifest hashes the queue, issuer triage and exchange notices used here.

The issuer check compares amount, record date and payment date; Chevron and
PepsiCo also publish a declaration date. UnitedHealth's September 2025
[announcement](https://www.unitedhealthgroup.com/newsroom/2025/2025-8-13-uhg-authorizes-payment-quarterly-dividend.html)
confirms the date that was absent from its summary history. The issuer pages
do not state an ex-date for these twelve events.

For ordinary US cash dividends, the [NYSE ex-date page](https://www.nyse.com/trade/ex-date-dividends)
and [Nasdaq rule](https://listingcenter.nasdaq.com/rulebook/nasdaq/rules/nasdaq-equity-11)
normally put the ex-date on a business-day record date. They also allow
exceptions. All twelve provider ex-dates equal their weekday record dates;
that is consistent with the normal rule, but the rule is not an event notice.

The separate `reference/dividend_ex_date_notices.csv` contains three dated
exchange notices. They confirm the same ex-date for two PepsiCo dividends
and one Chevron dividend on German trading venues. Those notices name the
security's US ISIN, but they do **not** prove the ex-date assigned to its US
listing. The review file labels the venue and keeps this evidence separate
from the US exchange rule.

## Outcome

| Events | Result | Reason |
| ---: | --- | --- |
| 2 Chevron | Hold | The provider declaration dates differ from Chevron's dividend history and [May](https://chevroncorp.gcs-web.com/news-releases/news-release-details/chevron-reports-first-quarter-2026-results) / [July](https://chevroncorp.gcs-web.com/node/38551) announcements. |
| 10 others | Awaiting review | Issuer-published event fields match, but no reviewer has signed off the US ex-date, event-date security identity and the two accounts' entitlement. |

The account quantities and signed candidate amounts are in `review.csv` so a
reviewer can see exactly what each decision would affect. They come from the
fictional fund's saved positions; they are not independent custodian evidence.

The existing May Chevron hold and the new August Chevron hold are recorded in
`decision_ledger_002.json`. Applying that ledger produced zero NAV differences:
both events remain pending. The other ten were awaiting review when this
packet was prepared. The one previously reviewed Mastercard event remained
the only approval in the dbt seed at that point.

Later on 6 October, the project owner approved the 5 December 2025 PepsiCo
entitlement using the documented rule-based ex-date and saved simulated
positions. [Its review note](pep_2025-12-05.md) and `decision_ledger_003.json`
record the decision. Nine of the ten matching events remain without a
decision. The original packet and ledger 002 remain as evidence of the
earlier review state.

Before approving any of these events, obtain a source that confirms the US
listing's event ex-date or a documented policy for deriving it, check the
security identity for the event date, and have a named reviewer sign the
account-level entitlement. Payment confirmation is a separate cash check;
an issuer pay date does not prove the fictional accounts received cash.
