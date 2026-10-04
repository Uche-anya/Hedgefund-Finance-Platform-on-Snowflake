provider "snowflake" {
  organization_name = "GXMGYTA"
  account_name      = "FQ45953"
  user              = "CHIGGZY"
  authenticator     = "USERNAMEPASSWORDMFA"
  role              = "ACCOUNTADMIN"
  warehouse         = "COMPUTE_WH"

  client_request_mfa_token          = "true"
  client_store_temporary_credential = "true"

  experimental_features_enabled = [
    "USER_ENABLE_DEFAULT_WORKLOAD_IDENTITY"
  ]
}
