from decimal import Decimal
import io
import unittest

from data_extraction.reference_rates import parse_ecb, parse_treasury


class ReferenceRateTests(unittest.TestCase):
    def test_ecb_cross_rate_inputs(self):
        text = ('TIME_PERIOD,OBS_VALUE,CURRENCY,CURRENCY_DENOM,FREQ,EXR_TYPE,EXR_SUFFIX\n'
                '2025-01-06,1.04,USD,EUR,D,SP00,A\n'
                '2025-01-06,0.83,GBP,EUR,D,SP00,A\n')
        rows = parse_ecb(text.encode(), ['2025-01-06'])
        self.assertEqual(Decimal(rows[0]['usd_per_eur']), Decimal('1.04'))
        self.assertEqual(Decimal(rows[0]['gbp_per_eur']), Decimal('0.83'))

    def test_treasury_one_month_rate(self):
        xml = b'''<feed xmlns:m="m" xmlns:d="d"><entry><content><m:properties>
        <d:NEW_DATE>2025-01-06T00:00:00</d:NEW_DATE><d:BC_1MONTH>4.44</d:BC_1MONTH>
        </m:properties></content></entry></feed>'''
        rows = parse_treasury(xml, ['2025-01-06'])
        self.assertEqual(Decimal(rows[0]['annual_rate_percent']), Decimal('4.44'))

    def test_missing_reference_date_fails(self):
        text = ('TIME_PERIOD,OBS_VALUE,CURRENCY,CURRENCY_DENOM,FREQ,EXR_TYPE,EXR_SUFFIX\n'
                '2025-01-06,1.04,USD,EUR,D,SP00,A\n')
        with self.assertRaisesRegex(ValueError, 'Missing ECB'):
            parse_ecb(text.encode(), ['2025-01-06'])
