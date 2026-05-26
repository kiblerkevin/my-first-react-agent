variable "prefix" {
  description = "Resource name prefix"
  type        = string
}

variable "aws_region" {
  description = "AWS region"
  type        = string
}

variable "dynamodb_table_arns" {
  description = "List of DynamoDB table ARNs"
  type        = list(string)
}

variable "secret_arn" {
  description = "Secrets Manager secret ARN"
  type        = string
}

variable "ses_domain_arn" {
  description = "SES domain identity ARN"
  type        = string
}
