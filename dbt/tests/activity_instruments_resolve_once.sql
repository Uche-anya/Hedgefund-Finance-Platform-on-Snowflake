with trades as (
    select event_id, market_ticker, business_date
    from {{ ref('stg_activity_events') }}
    where record_type = 'EXECUTION'
),
matches as (
    select t.event_id, count(i.security_id) as match_count
    from trades t
    left join {{ ref('dim_instrument') }} i
      on t.market_ticker = i.ticker
     and t.business_date between i.valid_from and i.valid_to
    group by t.event_id
)
select * from matches where match_count <> 1
