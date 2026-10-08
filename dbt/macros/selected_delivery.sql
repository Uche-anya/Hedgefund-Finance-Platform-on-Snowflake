{% macro selected_delivery(source_name, delivery_column) %}
    {% set request_id = var('close_request_id', '') %}
    {% if request_id %}
        exists (
            select 1
            from {{ source('operations', 'close_inputs') }} ci
            where ci.request_id = '{{ request_id }}'
              and ci.source_name = '{{ source_name }}'
              and ci.delivery_id = {{ delivery_column }}
        )
    {% elif target.name == 'prod' %}
        {{ exceptions.raise_compiler_error('A production close needs close_request_id') }}
    {% else %}
        1 = 1
    {% endif %}
{% endmacro %}
