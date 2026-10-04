with invalid_rows as (
    select security_id
    from {{ ref('dim_instrument') }}
    where instrument_version_id is null
       or security_id is null
       or ticker is null
       or share_class_figi is null
       or reviewed_issuer_cik is null
       or currency <> 'USD'
       or security_type <> 'CS'
       or valid_from is null
       or valid_to is null
       or valid_from > valid_to
       or is_current <> (valid_to = '9999-12-31')
),

version_counts as (
    select security_id, count_if(is_current) as current_versions
    from {{ ref('dim_instrument') }}
    group by security_id
),

replaced_securities as (
    select distinct predecessor_security_id as security_id
    from {{ ref('dim_instrument') }}
    where predecessor_security_id is not null
),

invalid_current_rows as (
    select c.security_id
    from version_counts c
    left join replaced_securities r on c.security_id = r.security_id
    where c.current_versions > 1
       or (c.current_versions = 0 and r.security_id is null)
)

select * from invalid_rows
union all
select * from invalid_current_rows
