provider "snowflake" {
  profile = var.snowflake_profile
  role    = "ACCOUNTADMIN"

  experimental_features_enabled = [
    "USER_ENABLE_DEFAULT_WORKLOAD_IDENTITY"
  ]
}
