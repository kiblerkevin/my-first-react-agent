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
        ResultSelector = {
          "score_count.$" = "$.score_count"
        }
        ResultPath = "$.fetchScores"
        Next       = "FetchArticles"
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
        ResultSelector = {
          "article_count.$"     = "$.article_count"
          "new_article_count.$" = "$.new_article_count"
        }
        ResultPath = "$.fetchArticles"
        Next       = "CheckNewArticles"
        Retry = [{
          ErrorEquals     = ["States.TaskFailed"]
          IntervalSeconds = 60
          MaxAttempts     = 3
          BackoffRate     = 2
        }]
      }
      CheckNewArticles = {
        Type = "Choice"
        Choices = [{
          Variable           = "$.fetchArticles.new_article_count"
          NumericGreaterThan = 0
          Next               = "DeduplicateArticles"
        }]
        Default = "SkipNoArticles"
      }
      SkipNoArticles = {
        Type    = "Succeed"
        Comment = "No new articles — workflow skipped."
      }
      DeduplicateArticles = {
        Type     = "Task"
        Resource = var.lambda_arns["deduplicate-articles"]
        ResultSelector = {
          "unique_count.$" = "$.unique_count"
        }
        ResultPath = "$.deduplicateArticles"
        Next       = "SummarizeArticles"
      }
      SummarizeArticles = {
        Type     = "Task"
        Resource = var.lambda_arns["summarize-articles"]
        ResultSelector = {
          "summary_count.$"  = "$.summary_count"
          "relevant_count.$" = "$.relevant_count"
        }
        ResultPath = "$.summarizeArticles"
        Next       = "CheckRelevant"
        Retry = [{
          ErrorEquals     = ["States.TaskFailed"]
          IntervalSeconds = 60
          MaxAttempts     = 3
          BackoffRate     = 2
        }]
      }
      CheckRelevant = {
        Type = "Choice"
        Choices = [{
          Variable           = "$.summarizeArticles.relevant_count"
          NumericGreaterThan = 0
          Next               = "CreateBlogDraft"
        }]
        Default = "SkipNoRelevant"
      }
      SkipNoRelevant = {
        Type    = "Succeed"
        Comment = "No relevant summaries — draft skipped."
      }
      CreateBlogDraft = {
        Type           = "Task"
        Resource       = var.lambda_arns["create-blog-draft"]
        TimeoutSeconds = 900
        ResultSelector = {
          "title.$"         = "$.title"
          "overall_score.$" = "$.overall_score"
          "summary_id.$"    = "$.summary_id"
        }
        ResultPath = "$.createBlogDraft"
        Next       = "CreateTaxonomy"
        Retry = [{
          ErrorEquals     = ["States.TaskFailed"]
          IntervalSeconds = 120
          MaxAttempts     = 2
          BackoffRate     = 2
        }]
      }
      CreateTaxonomy = {
        Type     = "Task"
        Resource = var.lambda_arns["create-taxonomy"]
        ResultSelector = {
          "category_count.$" = "$.category_count"
          "tag_count.$"      = "$.tag_count"
        }
        ResultPath = "$.createTaxonomy"
        Next       = "SendApprovalEmail"
      }
      SendApprovalEmail = {
        Type     = "Task"
        Resource = var.lambda_arns["send-approval-email"]
        ResultSelector = {
          "email_sent.$" = "$.email_sent"
          "token.$"      = "$.token"
        }
        ResultPath = "$.sendApprovalEmail"
        Next       = "Housekeeping"
      }
      Housekeeping = {
        Type     = "Task"
        Resource = var.lambda_arns["housekeeping"]
        ResultSelector = {
          "status.$" = "$.status"
        }
        ResultPath = "$.housekeeping"
        End        = true
      }
    }
  })
}
