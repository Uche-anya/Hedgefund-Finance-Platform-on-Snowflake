-- An empty delivery must fail even though column tests have no rows to reject.
select 'No prices found for the selected delivery' as problem
where not exists (select 1 from {{ ref('stg_closing_prices') }})
