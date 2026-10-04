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

Do not apply with local state. This configuration uses HCP Terraform to keep
one shared, locked state history. Create an HCP Terraform organization and a
CLI-driven workspace named `northbridge-snowflake`, then log in from this
computer. In the workspace's **Settings > General**, select **Local** execution
mode. HCP will store and lock state while Terraform continues to run on this
computer.

```powershell
terraform login
$env:TF_CLOUD_ORGANIZATION = 'northbridge-fund-anya'
$env:TF_WORKSPACE = 'northbridge-snowflake'
terraform -chdir=terraform/snowflake init
```

The HCP token is stored in Terraform's user-level credentials file, outside
this repository. The project wrapper supplies the Northbridge organization and
workspace on later commands.

## Adopt the existing CI objects

The CI role, service user, warehouse, monitor and schema already exist. Import
them before the first plan so Terraform adopts them rather than trying to
create replacements:

```powershell
python scripts/terraform_snowflake.py import snowflake_account_role.ci '"NORTHBRIDGE_DBT_CI"'
python scripts/terraform_snowflake.py import snowflake_service_user.github_ci '"NORTHBRIDGE_GITHUB_CI"'
python scripts/terraform_snowflake.py import snowflake_resource_monitor.ci '"NORTHBRIDGE_CI_MONITOR"'
python scripts/terraform_snowflake.py import snowflake_warehouse.ci '"NORTHBRIDGE_CI_WH"'
python scripts/terraform_snowflake.py import snowflake_schema.ci_dbt '"NORTHBRIDGE_CI_BASE"."DBT_CI"'
```

The first plan will also propose the production foundations. Use local
execution so the wrapper can read the administrator password from Windows
Credential Manager. Review the saved plan before applying it:

```powershell
python scripts/terraform_snowflake.py plan
python scripts/terraform_snowflake.py apply
```

The wrapper retrieves the same password as `snow_admin.py` from Windows
Credential Manager and passes it to Terraform only for the lifetime of the
process. `plan` writes `northbridge.tfplan`, and `apply` uses that exact saved
plan. Terraform assumes `ACCOUNTADMIN` while changing account-level
infrastructure. GitHub's CI and production deployment users receive the
smaller roles defined here.
