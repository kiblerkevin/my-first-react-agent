variable "prefix" {
  description = "Resource name prefix"
  type        = string
}

variable "lambda_arns" {
  description = "Map of Lambda function names to ARNs"
  type        = map(string)
}
