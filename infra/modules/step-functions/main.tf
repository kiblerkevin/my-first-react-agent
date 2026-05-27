resource "aws_iam_role" "step_functions" {
  name = "${var.prefix}-step-functions"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action = "sts:AssumeRole"
      Effect = "Allow"
      Principal = {
        Service = "states.amazonaws.com"
      }
    }]
  })
}

resource "aws_iam_role_policy" "step_functions_invoke" {
  name = "${var.prefix}-sfn-invoke-lambda"
  role = aws_iam_role.step_functions.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect   = "Allow"
      Action   = "lambda:InvokeFunction"
      Resource = values(var.lambda_arns)
    }]
  })
}

resource "aws_sfn_state_machine" "daily_workflow" {
  name     = "${var.prefix}-daily-workflow"
  role_arn = aws_iam_role.step_functions.arn

  definition = jsonencode({
    Comment = "Chicago Sports Recap daily workflow"
    StartAt = "FetchScores"
    States = {
      FetchScores = {
        Type     = "Task"
        Resource = var.lambda_arns["fetch-scores"]
        Next     = "FetchArticles"
        Retry = [{
          ErrorEquals     = ["States.TaskFailed"]
          IntervalSeconds = 60
          MaxAttempts     = 3
          BackoffRate     = 2
        }]
      }
      FetchArticles = {
        Type     = "Task"
        Resource = var.lambda_arns["fetch-articles"]
        Next     = "DeduplicateArticles"
        Retry = [{
          ErrorEquals     = ["States.TaskFailed"]
          IntervalSeconds = 60
          MaxAttempts     = 3
          BackoffRate     = 2
        }]
      }
      DeduplicateArticles = {
        Type     = "Task"
        Resource = var.lambda_arns["deduplicate-articles"]
        Next     = "SummarizeArticles"
      }
      SummarizeArticles = {
        Type     = "Task"
        Resource = var.lambda_arns["summarize-articles"]
        Next     = "CreateBlogDraft"
        Retry = [{
          ErrorEquals     = ["States.TaskFailed"]
          IntervalSeconds = 60
          MaxAttempts     = 3
          BackoffRate     = 2
        }]
      }
      CreateBlogDraft = {
        Type     = "Task"
        Resource = var.lambda_arns["create-blog-draft"]
        Next     = "CreateTaxonomy"
        Retry = [{
          ErrorEquals     = ["States.TaskFailed"]
          IntervalSeconds = 60
          MaxAttempts     = 2
          BackoffRate     = 2
        }]
      }
      CreateTaxonomy = {
        Type     = "Task"
        Resource = var.lambda_arns["create-taxonomy"]
        Next     = "SendApprovalEmail"
      }
      SendApprovalEmail = {
        Type     = "Task"
        Resource = var.lambda_arns["send-approval-email"]
        Next     = "Housekeeping"
      }
      Housekeeping = {
        Type     = "Task"
        Resource = var.lambda_arns["housekeeping"]
        End      = true
      }
    }
  })
}
