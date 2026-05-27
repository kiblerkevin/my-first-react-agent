locals {
  functions = {
    "fetch-scores" = {
      timeout     = 60
      memory_size = 256
    }
    "fetch-articles" = {
      timeout     = 120
      memory_size = 512
    }
    "deduplicate-articles" = {
      timeout     = 30
      memory_size = 256
    }
    "summarize-articles" = {
      timeout     = 300
      memory_size = 512
    }
    "create-blog-draft" = {
      timeout     = 300
      memory_size = 512
    }
    "create-taxonomy" = {
      timeout     = 30
      memory_size = 256
    }
    "send-approval-email" = {
      timeout     = 30
      memory_size = 256
    }
    "housekeeping" = {
      timeout     = 60
      memory_size = 256
    }
    "api-handler" = {
      timeout     = 30
      memory_size = 256
    }
  }
}

# Placeholder zip for initial deployment
data "archive_file" "placeholder" {
  type        = "zip"
  output_path = "${path.root}/.terraform/tmp/placeholder.zip"

  source {
    content  = "def handler(event, context): return {'statusCode': 200}"
    filename = "handler.py"
  }
}

resource "aws_lambda_layer_version" "deps" {
  layer_name          = "${var.prefix}-deps"
  filename            = data.archive_file.placeholder.output_path
  source_code_hash    = data.archive_file.placeholder.output_base64sha256
  compatible_runtimes = ["python3.12"]
  description         = "Shared dependencies layer"

  lifecycle {
    ignore_changes = [filename, source_code_hash]
  }
}

resource "aws_lambda_function" "functions" {
  for_each = local.functions

  function_name = "${var.prefix}-${each.key}"
  role          = var.execution_role_arn
  handler       = "handler.handler"
  runtime       = "python3.12"
  timeout       = each.value.timeout
  memory_size   = each.value.memory_size

  filename         = data.archive_file.placeholder.output_path
  source_code_hash = data.archive_file.placeholder.output_base64sha256

  layers = [aws_lambda_layer_version.deps.arn]

  environment {
    variables = var.environment_variables
  }

  lifecycle {
    ignore_changes = [filename, source_code_hash]
  }
}

resource "aws_cloudwatch_log_group" "lambda_logs" {
  for_each = local.functions

  name              = "/aws/lambda/${var.prefix}-${each.key}"
  retention_in_days = var.log_retention_days
}
