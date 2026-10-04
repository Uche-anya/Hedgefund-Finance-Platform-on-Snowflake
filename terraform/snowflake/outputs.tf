output "ci_identity" {
  value = {
    user      = snowflake_service_user.github_ci.name
    role      = snowflake_account_role.ci.name
    warehouse = snowflake_warehouse.ci.name
  }
}

output "production_identity" {
  value = {
    deploy_user  = snowflake_service_user.github_prod_deploy.name
    deploy_role  = snowflake_account_role.prod_deploy.name
    runtime_role = snowflake_account_role.prod_runtime.name
    database     = snowflake_database.prod.name
    warehouse    = snowflake_warehouse.prod.name
  }
}
