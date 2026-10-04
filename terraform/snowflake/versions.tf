terraform {
  required_version = ">= 1.10.0, < 2.0.0"

  required_providers {
    snowflake = {
      source  = "snowflakedb/snowflake"
      version = "2.21.0"
    }
  }

  # TF_CLOUD_ORGANIZATION and TF_WORKSPACE select the HCP location. Keeping
  # those personal account details out of Git also lets another contractor
  # adopt the same configuration without editing this file.
  cloud {}
}
