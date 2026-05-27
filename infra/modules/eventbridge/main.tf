resource "aws_iam_role" "eventbridge" {
  name = "${var.prefix}-eventbridge"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action = "sts:AssumeRole"
      Effect = "Allow"
      Principal = {
        Service = "scheduler.amazonaws.com"
      }
    }]
  })
}

resource "aws_iam_role_policy" "eventbridge_sfn" {
  name = "${var.prefix}-eventbridge-sfn"
  role = aws_iam_role.eventbridge.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect   = "Allow"
      Action   = "states:StartExecution"
      Resource = var.state_machine_arn
    }]
  })
}

resource "aws_scheduler_schedule" "daily_workflow" {
  name       = "${var.prefix}-daily-workflow"
  state      = var.enabled ? "ENABLED" : "DISABLED"
  group_name = "default"

  flexible_time_window {
    mode = "OFF"
  }

  schedule_expression          = "cron(0 6 * * ? *)"
  schedule_expression_timezone = "America/Chicago"

  target {
    arn      = var.state_machine_arn
    role_arn = aws_iam_role.eventbridge.arn
  }
}
