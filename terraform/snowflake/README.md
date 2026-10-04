# Snowflake infrastructure

This directory owns long-lived Snowflake foundations:

- CI and production roles
- GitHub OIDC service users
- X-Small warehouses and monthly credit monitors
- the production database and its three top-level schemas
- grants separating deployment from daily runtime

It does not own raw tables, dbt relations, Snowflake Tasks or the contents of
`NORTHBRIDGE_CI_BASE`. Raw DDL remains a database migration concern, dbt owns
analytical relations, and the CI base is refreshed as a reviewed clone.

## State comes first

Do not apply with local state. Copy `backend.hcl.example` to `backend.hcl` and
point it at a versioned, encrypted S3 bucket with state locking enabled. The
bucket must be created separately because Terraform cannot safely store the
state needed to create its own backend.

```powershell
terraform -chdir=terraform/snowflake init -backend-config=backend.hcl
```

## Adopt the existing CI objects

The CI role, service user, warehouse, monitor and schema already exist. Import
them before the first plan so Terraform adopts them rather than trying to
create replacements:

```powershell
terraform -chdir=terraform/snowflake import snowflake_account_role.ci '"NORTHBRIDGE_DBT_CI"'
terraform -chdir=terraform/snowflake import snowflake_service_user.github_ci '"NORTHBRIDGE_GITHUB_CI"'
terraform -chdir=terraform/snowflake import snowflake_resource_monitor.ci '"NORTHBRIDGE_CI_MONITOR"'
terraform -chdir=terraform/snowflake import snowflake_warehouse.ci '"NORTHBRIDGE_CI_WH"'
terraform -chdir=terraform/snowflake import snowflake_schema.ci_dbt '"NORTHBRIDGE_CI_BASE"."DBT_CI"'
```

The first plan will also propose the production foundations. Review that plan
before applying it:

```powershell
terraform -chdir=terraform/snowflake plan -out=northbridge.tfplan
terraform -chdir=terraform/snowflake apply northbridge.tfplan
```

Terraform uses the local `northbridge_admin` Snowflake profile and assumes
`ACCOUNTADMIN` only while changing account-level infrastructure. GitHub's CI
and production deployment users receive the smaller roles defined here.
