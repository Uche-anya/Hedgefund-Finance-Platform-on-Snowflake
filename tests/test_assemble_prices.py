import unittest

from data_extraction.assemble_prices import validate_mapping, validate_rows


def price(day, ticker="CHK"):
    return dict(valuation_date=day, source_ticker=ticker, instrument_id="EXAMPLE",
                share_class_figi="TEST", currency="USD", price_basis="unadjusted",
                open="10.25", high="11", low="10", close_price="10.50", volume="100")


class AssemblyTests(unittest.TestCase):
    def test_duplicate_missing_and_extra_dates_fail(self):
        expected = ["2024-10-01", "2024-10-02"]
        for dates in ([expected[0]], [expected[0], expected[0]], expected + ["2024-10-03"]):
            with self.subTest(dates=dates), self.assertRaises(ValueError):
                validate_rows("EXE", [price(d) for d in dates], expected)

    def test_short_history_is_checked_only_from_its_start(self):
        validate_rows("NEW", [price("2024-10-02")], ["2024-10-02"])

    def test_bad_price_and_wrong_basis_fail(self):
        for field, value in (("close_price", "12"), ("volume", "-1"),
                             ("open", "NaN"), ("currency", "EUR"),
                             ("price_basis", "adjusted")):
            with self.subTest(field=field), self.assertRaises(ValueError):
                validate_rows("EXE", [{**price("2024-10-01"), field: value}], ["2024-10-01"])

    def test_wrong_side_of_ticker_change_and_missing_identity_fail(self):
        mapping = [dict(ticker="CHK", **{"from": "2024-09-23", "to": "2024-10-01"}),
                   dict(ticker="EXE", **{"from": "2024-10-02", "to": "2024-10-03"})]
        rows = [price("2024-10-01"), price("2024-10-02", "EXE")]
        validate_mapping(rows, mapping)
        for field, value in (("source_ticker", "EXE"), ("instrument_id", ""),
                             ("share_class_figi", "OTHER")):
            with self.subTest(field=field), self.assertRaises(ValueError):
                validate_mapping([{**rows[0], field: value}, rows[1]], mapping)
