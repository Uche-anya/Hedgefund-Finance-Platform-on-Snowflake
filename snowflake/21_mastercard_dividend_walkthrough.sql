-- Read-only lesson: gross expected dividend based on shares entering the ex-date.
-- The issuer record date differs from Massive's. Keep both visible.
-- No cash receipt, tax, securities-lending claim or NAV entry is posted here.
with dividend as (
    select event_id, ticker, cash_amount, ex_dividend_date,
           record_date as provider_record_date, pay_date, currency
    from NORTHBRIDGE_DEV.DBT_DEV.STG_CORPORATE_ACTIONS
    where event_id = 'Ec6372be9137e6a822fd370e8f0738fc31cfb9db56ee95abb2ee9b45f3022db0b'
      and load_id = '890be0cfdcf2151ebb4aab47f0d53cd9'
), positions as (
    select account_id, business_date, market_ticker, currency, opening_quantity
    from NORTHBRIDGE_DEV.DBT_DEV.FCT_DAILY_POSITIONS
    where scenario_id = 'sim-replay-406bbef8179cdbb0a3dd6df3'
      and business_date = '2025-01-10'
      and market_ticker = 'MA'
)
select p.account_id,
       d.ticker,
       p.opening_quantity as shares_before_ex_date,
       d.cash_amount as dividend_per_share,
       p.opening_quantity * d.cash_amount as expected_gross_amount,
       case when p.opening_quantity > 0 then 'EXPECTED_RECEIVABLE'
            when p.opening_quantity < 0 then 'EXPECTED_SHORT_DIVIDEND_OBLIGATION'
            else 'NO_POSITION' end as estimate_type,
       d.ex_dividend_date,
       d.provider_record_date,
       '2025-01-09'::date as issuer_record_date,
       d.pay_date,
       'ILLUSTRATION_ONLY_NOT_POSTED_TO_NAV' as calculation_status
from positions p
left join dividend d
    on p.market_ticker = d.ticker and p.currency = d.currency
    and p.business_date = d.ex_dividend_date
order by p.account_id;
