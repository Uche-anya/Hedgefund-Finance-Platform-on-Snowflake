-- A data test returns the rows that break the rule. Zero rows means pass.
select *
from {{ ref('stg_executions') }}
where trim(execution_id) = ''

      or trim(instrument) = ''

      or quantity <= 0

      or business_date <> to_date('{{ var("business_date") }}', 'YYYY-MM-DD')

      or business_date_raw <> to_char(business_date, 'YYYY-MM-DD')
