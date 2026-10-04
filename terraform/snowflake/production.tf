resource "snowflake_database" "prod" {
  name                        = local.prod_database
  is_transient                = false
  data_retention_time_in_days = 1
  comment                     = "Production database for the Northbridge daily fund pipeline"
}

resource "snowflake_schema" "prod_raw" {
  database     = snowflake_database.prod.name
  name         = "RAW"
  is_transient = "false"
  comment      = "Immutable landing tables populated by production ingestion"
}

resource "snowflake_schema" "prod_dbt" {
  database     = snowflake_database.prod.name
  name         = "DBT_PROD"
  is_transient = "false"
  comment      = "Production relations built by dbt"
}

resource "snowflake_schema" "prod_operations" {
  database     = snowflake_database.prod.name
  name         = "OPERATIONS"
  is_transient = "false"
  comment      = "Production dbt project, tasks and operational audit records"
}

resource "snowflake_account_role" "prod_deploy" {
  name    = local.prod_deploy_role
  comment = "Deploys reviewed dbt code without running the daily pipeline"
}

resource "snowflake_account_role" "prod_runtime" {
  name    = local.prod_runtime_role
  comment = "Runs the production dbt project and scheduled daily task graph"
}

resource "snowflake_service_user" "github_prod_deploy" {
  name                           = local.prod_deploy_user
  login_name                     = local.prod_deploy_user
  display_name                   = local.prod_deploy_user
  comment                        = "GitHub Actions identity for reviewed production dbt deployments"
  default_role                   = snowflake_account_role.prod_deploy.name
  default_warehouse              = snowflake_warehouse.prod.name
  default_namespace              = "${snowflake_database.prod.name}.OPERATIONS"
  default_secondary_roles_option = "NONE"
  disabled                       = "false"

  default_workload_identity {
    oidc {
      issuer  = var.github_oidc_issuer
      subject = local.prod_oidc_subject
    }
  }
}

resource "snowflake_resource_monitor" "prod" {
  name            = local.prod_resource_monitor
  credit_quota    = var.prod_credit_quota
  frequency       = "MONTHLY"
  start_timestamp = "IMMEDIATELY"
  notify_triggers = [75]
  suspend_trigger = 100

  lifecycle {
    ignore_changes = [start_timestamp]
  }
}

resource "snowflake_warehouse" "prod" {
  name                      = local.prod_warehouse
  warehouse_type            = "STANDARD"
  warehouse_size            = "XSMALL"
  auto_suspend              = 60
  auto_resume               = "true"
  initially_suspended       = true
  min_cluster_count         = 1
  max_cluster_count         = 1
  scaling_policy            = "STANDARD"
  generation                = "2"
  enable_query_acceleration = "false"
  resource_monitor          = snowflake_resource_monitor.prod.fully_qualified_name
  comment                   = "Production compute for deployment and the daily close"
}

resource "snowflake_grant_account_role" "prod_deploy_to_user" {
  role_name = snowflake_account_role.prod_deploy.name
  user_name = snowflake_service_user.github_prod_deploy.name
}

resource "snowflake_grant_account_role" "prod_deploy_to_sysadmin" {
  role_name        = snowflake_account_role.prod_deploy.name
  parent_role_name = "SYSADMIN"
}

resource "snowflake_grant_account_role" "prod_runtime_to_sysadmin" {
  role_name        = snowflake_account_role.prod_runtime.name
  parent_role_name = "SYSADMIN"
}

resource "snowflake_grant_privileges_to_account_role" "prod_deploy_warehouse" {
  privileges        = ["USAGE"]
  account_role_name = snowflake_account_role.prod_deploy.name

  on_account_object {
    object_type = "WAREHOUSE"
    object_name = snowflake_warehouse.prod.name
  }
}

resource "snowflake_grant_privileges_to_account_role" "prod_deploy_database" {
  privileges        = ["USAGE"]
  account_role_name = snowflake_account_role.prod_deploy.name

  on_account_object {
    object_type = "DATABASE"
    object_name = snowflake_database.prod.name
  }
}

resource "snowflake_grant_privileges_to_account_role" "prod_deploy_operations" {
  privileges        = ["USAGE", "CREATE DBT PROJECT"]
  account_role_name = snowflake_account_role.prod_deploy.name

  on_schema {
    schema_name = snowflake_schema.prod_operations.fully_qualified_name
  }
}

resource "snowflake_grant_privileges_to_account_role" "prod_runtime_warehouse" {
  privileges        = ["USAGE"]
  account_role_name = snowflake_account_role.prod_runtime.name

  on_account_object {
    object_type = "WAREHOUSE"
    object_name = snowflake_warehouse.prod.name
  }
}

resource "snowflake_grant_privileges_to_account_role" "prod_runtime_database" {
  privileges        = ["USAGE"]
  account_role_name = snowflake_account_role.prod_runtime.name

  on_account_object {
    object_type = "DATABASE"
    object_name = snowflake_database.prod.name
  }
}

resource "snowflake_grant_privileges_to_account_role" "prod_runtime_raw" {
  privileges        = ["USAGE"]
  account_role_name = snowflake_account_role.prod_runtime.name

  on_schema {
    schema_name = snowflake_schema.prod_raw.fully_qualified_name
  }
}

resource "snowflake_grant_privileges_to_account_role" "prod_runtime_dbt" {
  privileges        = ["USAGE", "CREATE TABLE", "CREATE VIEW"]
  account_role_name = snowflake_account_role.prod_runtime.name

  on_schema {
    schema_name = snowflake_schema.prod_dbt.fully_qualified_name
  }
}

resource "snowflake_grant_privileges_to_account_role" "prod_runtime_operations" {
  privileges        = ["USAGE", "CREATE TABLE", "CREATE TASK"]
  account_role_name = snowflake_account_role.prod_runtime.name

  on_schema {
    schema_name = snowflake_schema.prod_operations.fully_qualified_name
  }
}

resource "snowflake_grant_privileges_to_account_role" "prod_runtime_raw_tables" {
  privileges        = ["SELECT"]
  account_role_name = snowflake_account_role.prod_runtime.name

  on_schema_object {
    future {
      object_type_plural = "TABLES"
      in_schema          = snowflake_schema.prod_raw.fully_qualified_name
    }
  }
}

resource "snowflake_grant_privileges_to_account_role" "prod_runtime_execute_task" {
  privileges        = ["EXECUTE TASK"]
  account_role_name = snowflake_account_role.prod_runtime.name
  on_account        = true
}
