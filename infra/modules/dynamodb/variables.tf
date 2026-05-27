variable "prefix" {
  description = "Resource name prefix"
  type        = string
}

variable "deletion_protection" {
  description = "Enable deletion protection on tables"
  type        = bool
  default     = false
}
