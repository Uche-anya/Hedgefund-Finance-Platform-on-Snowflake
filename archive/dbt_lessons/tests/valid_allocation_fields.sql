select *
from {{ ref('stg_allocations') }}
where trim(allocation_id) = ''

      or trim(execution_id) = ''

      or trim(portfolio) = ''

      or quantity <= 0

      or business_date <> to_date('{{ var("business_date") }}', 'YYYY-MM-DD')

      or business_date_raw <> to_char(business_date, 'YYYY-MM-DD')
