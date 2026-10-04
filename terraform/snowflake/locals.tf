locals {
  ci_role             = "NORTHBRIDGE_DBT_CI"
  ci_user             = "NORTHBRIDGE_GITHUB_CI"
  ci_warehouse        = "NORTHBRIDGE_CI_WH"
  ci_resource_monitor = "NORTHBRIDGE_CI_MONITOR"

  prod_database         = "NORTHBRIDGE_PROD"
  prod_deploy_role      = "NORTHBRIDGE_DBT_PROD_DEPLOY"
  prod_runtime_role     = "NORTHBRIDGE_DBT_PROD"
  prod_deploy_user      = "NORTHBRIDGE_GITHUB_PROD_DEPLOY"
  prod_warehouse        = "NORTHBRIDGE_PROD_WH"
  prod_resource_monitor = "NORTHBRIDGE_PROD_MONITOR"

  ci_oidc_subject   = "repo:${var.github_repository_subject}:environment:ci"
  prod_oidc_subject = "repo:${var.github_repository_subject}:environment:production"
}
