import unittest

from scripts.load_daily_prices import check_replacement


class PriceCorrectionTests(unittest.TestCase):
    def test_second_delivery_names_its_predecessor(self):
        old = {'daily-prices-old'}
        correction = {'delivery_id': 'daily-prices-new',
                      'replaces_delivery_id': 'daily-prices-old'}
        check_replacement(old, correction)
        with self.assertRaisesRegex(ValueError, 'name it'):
            check_replacement(old, {'delivery_id': 'daily-prices-new'})
        with self.assertRaisesRegex(ValueError, 'not in RAW'):
            check_replacement(old, dict(correction,
                                        replaces_delivery_id='unknown'))

    def test_same_delivery_can_be_retried(self):
        check_replacement({'daily-prices-old'},
                          {'delivery_id': 'daily-prices-old'})


if __name__ == '__main__':
    unittest.main()
