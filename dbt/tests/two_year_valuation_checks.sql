{{ config(tags=['fixture']) }}

-- The signed position values must reproduce each account's market value.
with positions as (
    select scenario_id, ledger_id, business_date, account_id,
        sum(market_value_usd) as net_value,
        sum(abs(market_value_usd)) as gross_value
    from {{ ref('cmp_python_position_day') }}
    group by 1, 2, 3, 4
)
select a.scenario_id, a.ledger_id, a.business_date, a.account_id
from {{ ref('cmp_python_account_day') }} a
left join positions p
  on a.scenario_id = p.scenario_id and a.ledger_id = p.ledger_id
 and a.business_date = p.business_date and a.account_id = p.account_id
where abs(a.net_market_value_usd - coalesce(p.net_value, 0)) > 0.000001
   or abs(a.gross_market_exposure_usd - coalesce(p.gross_value, 0)) > 0.000001
   or abs(a.illustrative_nav_usd - a.reviewed_nav_usd
          - a.pending_candidate_impact_usd) > 0.000001
