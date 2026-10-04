resource "snowflake_account_role" "ci" {
  name    = local.ci_role
  comment = "Builds and tests pull-request dbt code in disposable database clones"
}

resource "snowflake_service_user" "github_ci" {
  name                           = local.ci_user
  login_name                     = local.ci_user
  display_name                   = local.ci_user
  comment                        = "GitHub Actions identity for Northbridge pull-request checks"
  default_role                   = snowflake_account_role.ci.name
  default_warehouse              = snowflake_warehouse.ci.name
  default_namespace              = "${var.ci_base_database}.OPERATIONS"
  default_secondary_roles_option = "NONE"
  disabled                       = "false"

  default_workload_identity {
    oidc {
      issuer  = var.github_oidc_issuer
      subject = local.ci_oidc_subject
    }
  }
}

resource "snowflake_resource_monitor" "ci" {
  name            = local.ci_resource_monitor
  credit_quota    = var.ci_credit_quota
  frequency       = "MONTHLY"
  start_timestamp = "IMMEDIATELY"
  notify_triggers = [75]
  suspend_trigger = 100

  lifecycle {
    ignore_changes = [start_timestamp]
  }
}

resource "snowflake_warehouse" "ci" {
  name                      = local.ci_warehouse
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
  resource_monitor          = snowflake_resource_monitor.ci.fully_qualified_name
  comment                   = "Small warehouse for pull-request dbt builds"
}

# The base is deliberately not a Terraform database resource. It is a data
# snapshot refreshed with Snowflake CLONE, while Terraform manages its schema.
resource "snowflake_schema" "ci_dbt" {
  database            = var.ci_base_database
  name                = "DBT_CI"
  is_transient        = "false"
  with_managed_access = "false"
  comment             = "Destination schema inherited by pull-request database clones"
}

resource "snowflake_grant_account_role" "ci_to_user" {
  role_name = snowflake_account_role.ci.name
  user_name = snowflake_service_user.github_ci.name
}

resource "snowflake_grant_account_role" "ci_to_sysadmin" {
  role_name        = snowflake_account_role.ci.name
  parent_role_name = "SYSADMIN"
}

resource "snowflake_grant_privileges_to_account_role" "ci_create_database" {
  privileges        = ["CREATE DATABASE"]
  account_role_name = snowflake_account_role.ci.name
  on_account        = true
}

resource "snowflake_grant_privileges_to_account_role" "ci_warehouse_usage" {
  privileges        = ["USAGE"]
  account_role_name = snowflake_account_role.ci.name

  on_account_object {
    object_type = "WAREHOUSE"
    object_name = snowflake_warehouse.ci.name
  }
}

resource "snowflake_grant_privileges_to_account_role" "ci_database_usage" {
  privileges        = ["USAGE"]
  account_role_name = snowflake_account_role.ci.name

  on_account_object {
    object_type = "DATABASE"
    object_name = var.ci_base_database
  }
}

resource "snowflake_grant_privileges_to_account_role" "ci_schema_usage" {
  privileges        = ["USAGE"]
  account_role_name = snowflake_account_role.ci.name

  on_schema {
    all_schemas_in_database = var.ci_base_database
  }
}

resource "snowflake_grant_privileges_to_account_role" "ci_all_tables" {
  privileges        = ["SELECT"]
  account_role_name = snowflake_account_role.ci.name

  on_schema_object {
    all {
      object_type_plural = "TABLES"
      in_database        = var.ci_base_database
    }
  }
}

resource "snowflake_grant_privileges_to_account_role" "ci_all_views" {
  privileges        = ["SELECT"]
  account_role_name = snowflake_account_role.ci.name

  on_schema_object {
    all {
      object_type_plural = "VIEWS"
      in_database        = var.ci_base_database
    }
  }
}

resource "snowflake_grant_privileges_to_account_role" "ci_dbt_schema" {
  privileges        = ["USAGE", "CREATE TABLE", "CREATE VIEW"]
  account_role_name = snowflake_account_role.ci.name

  on_schema {
    schema_name = snowflake_schema.ci_dbt.fully_qualified_name
  }
}

resource "snowflake_grant_privileges_to_account_role" "ci_dbt_project" {
  privileges        = ["CREATE DBT PROJECT"]
  account_role_name = snowflake_account_role.ci.name

  on_schema {
    schema_name = "\"${var.ci_base_database}\".\"OPERATIONS\""
  }
}
