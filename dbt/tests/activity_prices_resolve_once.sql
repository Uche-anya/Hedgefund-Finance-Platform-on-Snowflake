with replay_tickers as (
    select distinct market_ticker as ticker
    from {{ ref('stg_activity_events') }}
    where record_type = 'EXECUTION'
),
matches as (
    select p.universe_ticker, p.valuation_date, count(i.security_id) as match_count
    from {{ ref('stg_historical_prices') }} p
    join replay_tickers r on p.universe_ticker = r.ticker
    left join {{ ref('dim_instrument') }} i
      on p.universe_ticker = i.ticker
     and p.valuation_date between i.valid_from and i.valid_to
    group by p.universe_ticker, p.valuation_date
)
select * from matches where match_count <> 1
