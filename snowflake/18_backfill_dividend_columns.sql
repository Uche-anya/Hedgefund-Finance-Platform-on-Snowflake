-- Existing development closes predate dividend booking. Fill only rows that
-- have no booked event on or before their valuation date.
UPDATE NORTHBRIDGE_DEV.DBT_DEV.FCT_CASH_DAILY c
SET modeled_dividend_cash_to_date = 0
WHERE modeled_dividend_cash_to_date IS NULL
  AND NOT EXISTS (
      SELECT 1 FROM NORTHBRIDGE_DEV.DBT_DEV.FCT_DIVIDEND_EXPOSURE e
      WHERE e.scenario_id = c.scenario_id
        AND e.account_id = c.account_id
        AND e.ex_dividend_date <= c.valuation_date
  );

UPDATE NORTHBRIDGE_DEV.DBT_DEV.FCT_NAV_DAILY n
SET dividend_receivable_usd = 0,
    dividend_liability_usd = 0,
    dividend_pnl_usd = 0
WHERE (dividend_receivable_usd IS NULL OR dividend_liability_usd IS NULL
       OR dividend_pnl_usd IS NULL)
  AND NOT EXISTS (
      SELECT 1 FROM NORTHBRIDGE_DEV.DBT_DEV.FCT_DIVIDEND_EXPOSURE e
      WHERE e.scenario_id = n.scenario_id
        AND e.account_id = n.account_id
        AND e.ex_dividend_date <= n.valuation_date
  );
