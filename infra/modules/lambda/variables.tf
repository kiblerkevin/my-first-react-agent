variable "prefix" {
  description = "Resource name prefix"
  type        = string
}

variable "aws_region" {
  description = "AWS region"
  type        = string
}

variable "execution_role_arn" {
  description = "IAM role ARN for Lambda execution"
  type        = string
}

variable "secret_arn" {
  description = "Secrets Manager secret ARN"
  type        = string
}

variable "log_retention_days" {
  description = "CloudWatch log retention in days"
  type        = number
  default     = 14
}

variable "environment_variables" {
  description = "Environment variables for Lambda functions"
  type        = map(string)
  default     = {}
}
