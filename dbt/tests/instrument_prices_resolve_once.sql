with mastered_prices as (
    select p.*
    from {{ ref('stg_historical_prices') }} p
    where exists (
        select 1
        from {{ ref('dim_instrument') }} i
        where p.share_class_figi = i.share_class_figi
           or (p.share_class_figi is null and p.source_ticker = i.ticker)
    )
),

matches as (
    select
        p.source_ticker,
        p.valuation_date,
        count(i.instrument_version_id) as match_count
    from mastered_prices p
    left join {{ ref('dim_instrument') }} i
      on (p.share_class_figi = i.share_class_figi
          or (p.share_class_figi is null and p.source_ticker = i.ticker))
     and p.valuation_date between i.valid_from and i.valid_to
    group by p.source_ticker, p.valuation_date
)

select * from matches where match_count <> 1
