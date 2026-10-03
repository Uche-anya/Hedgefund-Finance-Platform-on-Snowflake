import unittest

from data_extraction.inspect_replay_instruments import TICKERS, review


def row(ticker):
    return {
        "requested_ticker": ticker,
        "as_of_date": "2025-01-10",
        "name": ticker + " test company",
        "cik": "CIK-" + ticker,
        "composite_figi": "COMPOSITE-" + ticker,
        "share_class_figi": "SHARE-" + ticker,
        "primary_exchange": "XNAS",
        "type": "CS",
        "currency_name": "usd",
        "active": "True",
    }


class ReplayInstrumentReviewTests(unittest.TestCase):
    def test_complete_unique_common_stocks_are_ready_for_review(self):
        result = review([row(ticker) for ticker in TICKERS])
        self.assertEqual(len(result), 20)
        self.assertTrue(all(item["review_status"] == "READY_FOR_REVIEW" for item in result))

    def test_missing_or_reused_figi_is_not_ready(self):
        rows = [row(ticker) for ticker in TICKERS]
        rows[0]["share_class_figi"] = ""
        rows[1]["share_class_figi"] = rows[2]["share_class_figi"]
        result = {item["ticker"]: item for item in review(rows)}
        self.assertEqual(result[TICKERS[0]]["review_status"], "MISSING_IDENTIFIER")
        self.assertEqual(result[TICKERS[1]]["review_status"], "REVIEW_CONFLICT")
        self.assertEqual(result[TICKERS[2]]["review_status"], "REVIEW_CONFLICT")

    def test_missing_replay_ticker_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "20 replay tickers"):
            review([row(ticker) for ticker in TICKERS[:-1]])


if __name__ == "__main__":
    unittest.main()
