import io
import json
import unittest
from unittest.mock import patch

from pipeline.security_reference import get_ticker


class SecurityReferenceTests(unittest.TestCase):
    def test_provider_cannot_answer_with_a_different_ticker(self):
        response = {"status": "OK", "results": {"ticker": "OTHER"}}
        body = io.BytesIO(json.dumps(response).encode("utf-8"))
        with patch("pipeline.security_reference.urlopen", return_value=body):
            with self.assertRaisesRegex(ValueError, "changed symbol"):
                get_ticker("PG", "2026-10-14", "test-key")


if __name__ == "__main__":
    unittest.main()
