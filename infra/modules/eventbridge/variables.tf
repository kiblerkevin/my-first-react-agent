variable "prefix" {
  description = "Resource name prefix"
  type        = string
}

variable "enabled" {
  description = "Whether the schedule is enabled"
  type        = bool
  default     = false
}

variable "state_machine_arn" {
  description = "Step Functions state machine ARN to trigger"
  type        = string
}
