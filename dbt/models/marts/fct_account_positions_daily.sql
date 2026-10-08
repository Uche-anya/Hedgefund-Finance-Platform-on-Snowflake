-- Rebuild daily shares from the two-year OMS feed, then mark them to market.
-- A predecessor and its one-for-one successor share one running position key.
with trades as (
    select
        e.scenario_id,
        e.business_date,
        e.account_id,
        coalesce(i.predecessor_security_id, i.security_id) as position_key,
        case when e.side = 'BUY' then e.quantity else -e.quantity end as shares
    from {{ ref('stg_oms_events') }} e
    join {{ ref('dim_instrument') }} i
      on e.market_ticker = i.ticker
     and e.business_date between i.valid_from and i.valid_to
    where e.scenario_id = '{{ var("scenario_id") }}'
      and e.execution_status = 'ACTIVE'
      and e.currency = 'USD'
),
daily_trades as (
    select scenario_id, business_date, account_id, position_key,
           sum(shares) as shares_traded
    from trades
    group by 1, 2, 3, 4
),
dated_prices as (
    select
        p.valuation_date as business_date,
        i.security_id,
        i.instrument_version_id,
        i.ticker,
        i.security_name,
        coalesce(i.predecessor_security_id, i.security_id) as position_key,
        p.close_price
    from {{ ref('stg_historical_prices') }} p
    join {{ ref('dim_instrument') }} i
      on p.universe_ticker = i.ticker
     and p.valuation_date between i.valid_from and i.valid_to
     and (p.share_class_figi = i.share_class_figi or p.share_class_figi is null)
    where p.currency = 'USD' and p.price_basis = 'unadjusted'
      and p.universe_ticker in (select distinct market_ticker
                                from {{ ref('stg_oms_events') }}
                                where scenario_id = '{{ var("scenario_id") }}')
),
accounts as (
    select distinct scenario_id, account_id from trades
),
daily_grid as (
    select a.scenario_id, a.account_id, p.business_date, p.security_id,
           p.instrument_version_id, p.ticker, p.security_name,
           p.position_key, p.close_price,
           coalesce(t.shares_traded, 0) as shares_traded
    from accounts a
    cross join dated_prices p
    left join daily_trades t
      on t.scenario_id = a.scenario_id and t.account_id = a.account_id
     and t.business_date = p.business_date and t.position_key = p.position_key
),
running as (
    select *,
           sum(shares_traded) over (
               partition by scenario_id, account_id, position_key
               order by business_date rows between unbounded preceding and current row
           ) as quantity
    from daily_grid
)
select scenario_id, business_date, account_id, security_id,
       instrument_version_id, ticker as ticker_as_of_date,
       security_name as security_name_as_of_date,
       case when quantity > 0 then 'LONG' else 'SHORT' end as position_side,
       quantity, close_price as close_price_usd,
       quantity * close_price as market_value_usd
from running
where quantity <> 0
