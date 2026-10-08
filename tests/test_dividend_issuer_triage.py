import unittest

from scripts.triage_two_year_dividends import compare


class IssuerTriageTests(unittest.TestCase):
    def setUp(self):
        self.provider = {
            'record_date': '2026-05-19', 'pay_date': '2026-06-10',
            'declaration_date': '2026-04-29', 'ex_dividend_date': '2026-05-19',
            'cash_amount': 1.78,
        }
        self.issuer = {
            'record_date': '2026-05-19', 'pay_date': '2026-06-10',
            'declared_date': '2026-05-01', 'ex_dividend_date': '',
            'cash_per_share_usd': '1.78',
        }

    def test_conflict_keeps_missing_ex_date_visible(self):
        status, conflict, missing = compare(self.provider, self.issuer)
        self.assertEqual((status, conflict, missing),
                         ('ISSUER_CONFLICT', 'declaration_date', 'ex_dividend_date'))

    def test_match_is_partial_without_issuer_ex_date(self):
        self.provider['declaration_date'] = '2026-05-01'
        status, conflict, missing = compare(self.provider, self.issuer)
        self.assertEqual((status, conflict, missing),
                         ('PARTIAL_ISSUER_MATCH', '', 'ex_dividend_date'))

    def test_no_evidence_is_not_a_match(self):
        self.assertEqual(compare(self.provider, None),
                         ('NO_ISSUER_EVIDENCE', '', ''))


if __name__ == '__main__':
    unittest.main()
