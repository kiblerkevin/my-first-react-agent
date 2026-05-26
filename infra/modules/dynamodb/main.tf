resource "aws_dynamodb_table" "articles" {
  name         = "${var.prefix}-articles"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "url"

  attribute {
    name = "url"
    type = "S"
  }

  attribute {
    name = "team"
    type = "S"
  }

  attribute {
    name = "fetched_at"
    type = "S"
  }

  global_secondary_index {
    name            = "team-fetched_at-index"
    hash_key        = "team"
    range_key       = "fetched_at"
    projection_type = "ALL"
  }

  deletion_protection_enabled = var.deletion_protection
  point_in_time_recovery {
    enabled = true
  }
}

resource "aws_dynamodb_table" "article_summaries" {
  name         = "${var.prefix}-article-summaries"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "url"

  attribute {
    name = "url"
    type = "S"
  }

  attribute {
    name = "team"
    type = "S"
  }

  attribute {
    name = "created_at"
    type = "S"
  }

  global_secondary_index {
    name            = "team-created_at-index"
    hash_key        = "team"
    range_key       = "created_at"
    projection_type = "ALL"
  }

  deletion_protection_enabled = var.deletion_protection
  point_in_time_recovery {
    enabled = true
  }
}

resource "aws_dynamodb_table" "summaries" {
  name         = "${var.prefix}-summaries"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "id"

  attribute {
    name = "id"
    type = "S"
  }

  attribute {
    name = "created_at"
    type = "S"
  }

  global_secondary_index {
    name            = "created_at-index"
    hash_key        = "created_at"
    projection_type = "ALL"
  }

  deletion_protection_enabled = var.deletion_protection
  point_in_time_recovery {
    enabled = true
  }
}

resource "aws_dynamodb_table" "pending_approvals" {
  name         = "${var.prefix}-pending-approvals"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "token"

  attribute {
    name = "token"
    type = "S"
  }

  attribute {
    name = "status"
    type = "S"
  }

  attribute {
    name = "created_at"
    type = "S"
  }

  global_secondary_index {
    name            = "status-created_at-index"
    hash_key        = "status"
    range_key       = "created_at"
    projection_type = "ALL"
  }

  deletion_protection_enabled = var.deletion_protection
  point_in_time_recovery {
    enabled = true
  }
}

resource "aws_dynamodb_table" "workflow_runs" {
  name         = "${var.prefix}-workflow-runs"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "run_id"

  attribute {
    name = "run_id"
    type = "S"
  }

  attribute {
    name = "status"
    type = "S"
  }

  attribute {
    name = "started_at"
    type = "S"
  }

  global_secondary_index {
    name            = "status-started_at-index"
    hash_key        = "status"
    range_key       = "started_at"
    projection_type = "ALL"
  }

  deletion_protection_enabled = var.deletion_protection
  point_in_time_recovery {
    enabled = true
  }
}

resource "aws_dynamodb_table" "drift_alerts" {
  name         = "${var.prefix}-drift-alerts"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "id"

  attribute {
    name = "id"
    type = "S"
  }

  attribute {
    name = "status"
    type = "S"
  }

  attribute {
    name = "triggered_at"
    type = "S"
  }

  global_secondary_index {
    name            = "status-triggered_at-index"
    hash_key        = "status"
    range_key       = "triggered_at"
    projection_type = "ALL"
  }

  deletion_protection_enabled = var.deletion_protection
  point_in_time_recovery {
    enabled = true
  }
}

resource "aws_dynamodb_table" "oauth_tokens" {
  name         = "${var.prefix}-oauth-tokens"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "service"

  attribute {
    name = "service"
    type = "S"
  }

  deletion_protection_enabled = var.deletion_protection
  point_in_time_recovery {
    enabled = true
  }
}
