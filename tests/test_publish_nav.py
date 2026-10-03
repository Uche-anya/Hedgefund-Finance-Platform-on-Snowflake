import unittest

from decimal import Decimal

from scripts.publish_nav import candidate_hash, publication_id, run_id


class NavPublicationTests(unittest.TestCase):
    def test_same_inputs_make_the_same_ids(self):
        config = {
            'business_date': '2025-01-30',
            'scenario_id': 'scenario',
            'replay_delivery_id': 'replay',
            'price_delivery_id': 'prices',
            'broker_delivery_id': 'broker',
        }
        first = run_id(config, 'code-version')
        self.assertEqual(first, run_id(config, 'code-version'))
        self.assertEqual(publication_id(first, 'ACCOUNT-1', 'USD'),
                         publication_id(first, 'ACCOUNT-1', 'USD'))
        self.assertNotEqual(first, run_id(config, 'changed-code'))

    def test_candidate_hash_changes_with_nav(self):
        rows = [('S', '2025-01-30', 'A', 'USD', Decimal('100.000000000'), 'BASIS')]
        first = candidate_hash(rows)
        changed = [('S', '2025-01-30', 'A', 'USD', Decimal('100.010000000'), 'BASIS')]
        self.assertNotEqual(first, candidate_hash(changed))


if __name__ == '__main__':
    unittest.main()
