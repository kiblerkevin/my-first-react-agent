variable "project" {
  description = "Project name used for resource naming"
  type        = string
  default     = "chicago-sports-recap"
}

variable "environment" {
  description = "Deployment environment (dev or prod)"
  type        = string

  validation {
    condition     = contains(["dev", "prod"], var.environment)
    error_message = "Environment must be dev or prod."
  }
}

variable "aws_region" {
  description = "Primary AWS region"
  type        = string
  default     = "us-west-1"
}

variable "domain" {
  description = "Root domain for the application"
  type        = string
}

variable "eventbridge_enabled" {
  description = "Whether to enable the EventBridge scheduler"
  type        = bool
  default     = false
}

variable "lambda_log_retention_days" {
  description = "CloudWatch log retention in days"
  type        = number
  default     = 14
}

variable "dynamodb_deletion_protection" {
  description = "Enable deletion protection on DynamoDB tables"
  type        = bool
  default     = false
}

variable "auth0_issuer" {
  description = "Auth0 issuer URL for JWT validation"
  type        = string
}

variable "auth0_audience" {
  description = "Auth0 audience for JWT validation"
  type        = string
}
