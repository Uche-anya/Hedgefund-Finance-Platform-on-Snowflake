terraform {
  required_version = ">= 1.10.0, < 2.0.0"

  required_providers {
    snowflake = {
      source  = "snowflakedb/snowflake"
      version = "2.21.0"
    }
  }

  backend "s3" {}
}
