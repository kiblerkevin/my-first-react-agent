variable "prefix" {
  description = "Resource name prefix"
  type        = string
}

variable "domain" {
  description = "Root domain"
  type        = string
}

variable "spa_bucket_id" {
  description = "S3 bucket ID for SPA"
  type        = string
}

variable "spa_bucket_arn" {
  description = "S3 bucket ARN for SPA"
  type        = string
}

variable "spa_bucket_regional_domain_name" {
  description = "S3 bucket regional domain name"
  type        = string
}

variable "acm_cert_arn" {
  description = "ACM certificate ARN (us-east-1). Empty string to skip distribution."
  type        = string
  default     = ""
}

variable "waf_web_acl_arn" {
  description = "WAF WebACL ARN"
  type        = string
}
