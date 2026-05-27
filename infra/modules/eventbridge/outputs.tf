output "schedule_arn" {
  description = "ARN of the EventBridge schedule"
  value       = aws_scheduler_schedule.daily_workflow.arn
}
