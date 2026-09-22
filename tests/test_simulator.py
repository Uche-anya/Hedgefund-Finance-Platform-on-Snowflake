import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from datetime import datetime

from simulator import create_execution, produce_trades, save_event, validate_execution


class SimulatorTests(unittest.TestCase):
    def test_producer_saves_five_distinct_trades_with_four_pauses(self):
        with tempfile.TemporaryDirectory() as folder:
            with patch("simulator.time.sleep") as sleep, patch("builtins.print"):
                produce_trades(Path(folder))
            events = [json.loads(path.read_text()) for path in Path(folder).glob("*.jsonl")]
            events.sort(key=lambda event: event["executed_at"])
            self.assertEqual(len(events), 5)
            for field in ("event_id", "execution_id", "order_id"):
                self.assertEqual(len({event[field] for event in events}), 5)
            self.assertEqual(
                [(event["instrument_id"], event["side"], event["quantity"]) for event in events],
                [("AAPL.US", "BUY", "10"), ("AMZN.US", "SELL", "5"),
                 ("AAPL.US", "BUY", "8"), ("AMZN.US", "BUY", "2"),
                 ("AAPL.US", "SELL", "3")],
            )
            for previous, current in zip(events, events[1:]):
                gap = (datetime.fromisoformat(current["executed_at"])
                       - datetime.fromisoformat(previous["executed_at"]))
                self.assertEqual(gap.total_seconds(), 2)
            self.assertEqual(sleep.call_count, 4)
            for call in sleep.call_args_list:
                self.assertEqual(call.args, (2,))

    def test_valid_buy_and_sell_save_without_changing_values(self):
        with tempfile.TemporaryDirectory() as folder:
            for side in ("BUY", "SELL"):
                event = create_execution()
                event["side"] = side
                event["quantity"] = "0.5"
                path = save_event(event, Path(folder))
                self.assertEqual(json.loads(path.read_text()), event)
                with self.assertRaises(FileExistsError):
                    save_event(event, Path(folder))

    def test_missing_ids_and_bad_fields_are_rejected(self):
        cases = [
            ("execution_id", None), ("order_id", "  "),
            ("event_id", "../outside"), ("side", "PURCHASE"),
            ("quantity", "-10"), ("quantity", "NaN"),
            ("quantity", "Infinity"), ("quantity", 10),
            ("execution_price", "0"), ("execution_price", "oops"),
            ("executed_at", "yesterday"),
            ("executed_at", "2025-01-06T15:00:01"),
            ("published_at", "2025-01-06T14:00:00Z"),
            ("business_date", "2025-02-30"),
            ("settlement_due", "2025-01-05"),
            ("execution_version", True), ("execution_version", 2),
            ("is_simulated", False), ("currency", "GBP"),
            ("event_type", "EXECUTION_CORRECTED"),
        ]
        for field, value in cases:
            with self.subTest(field=field, value=value):
                event = create_execution()
                event[field] = value
                with self.assertRaises(ValueError):
                    validate_execution(event)
        event = create_execution()
        del event["execution_id"]
        with self.assertRaisesRegex(ValueError, "execution_id"):
            validate_execution(event)

    def test_invalid_event_creates_no_output(self):
        with tempfile.TemporaryDirectory() as folder:
            output = Path(folder) / "events"
            event = create_execution()
            event["quantity"] = "-10"
            with self.assertRaisesRegex(ValueError, "quantity"):
                save_event(event, output)
            self.assertFalse(output.exists())

    def test_timestamp_order_compares_instants_across_timezones(self):
        event = create_execution()
        event["published_at"] = "2025-01-06T10:00:01.180-05:00"
        validate_execution(event)


if __name__ == "__main__":
    unittest.main()
