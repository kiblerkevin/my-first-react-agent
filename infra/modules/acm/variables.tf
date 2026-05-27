variable "domain" {
  description = "Root domain"
  type        = string
}

variable "prefix" {
  description = "Resource name prefix"
  type        = string
}

variable "aws_region" {
  description = "Primary AWS region"
  type        = string
}

variable "wait_for_validation" {
  description = "Whether to wait for ACM certificate validation (set to true after adding DNS records)"
  type        = bool
  default     = false
}
