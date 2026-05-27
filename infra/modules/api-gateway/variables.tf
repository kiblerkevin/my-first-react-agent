variable "prefix" {
  description = "Resource name prefix"
  type        = string
}

variable "api_lambda_arn" {
  description = "ARN of the API handler Lambda function"
  type        = string
}

variable "api_lambda_invoke_arn" {
  description = "Invoke ARN of the API handler Lambda function"
  type        = string
}

variable "auth0_issuer" {
  description = "Auth0 issuer URL"
  type        = string
}

variable "auth0_audience" {
  description = "Auth0 audience"
  type        = string
}

variable "domain" {
  description = "Root domain"
  type        = string
}

variable "acm_cert_arn" {
  description = "ACM certificate ARN for the API custom domain"
  type        = string
}
