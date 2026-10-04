variable "github_oidc_issuer" {
  description = "Issuer used by GitHub Actions OIDC tokens."
  type        = string
  default     = "https://token.actions.githubusercontent.com"
}

variable "github_repository_subject" {
  description = "Immutable GitHub owner and repository identity used in OIDC subjects."
  type        = string
  default     = "Uche-anya@108993926/Hedgefund-Finance-Platform-on-Snowflake@1379734472"
}

variable "ci_base_database" {
  description = "Reviewed snapshot cloned for pull-request builds. Its refresh is handled outside Terraform."
  type        = string
  default     = "NORTHBRIDGE_CI_BASE"
}

variable "ci_credit_quota" {
  description = "Monthly credit ceiling for pull-request builds."
  type        = number
  default     = 2
}

variable "prod_credit_quota" {
  description = "Initial monthly credit ceiling for the production warehouse."
  type        = number
  default     = 5
}
