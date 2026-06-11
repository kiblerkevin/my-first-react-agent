output "table_arns" {
  description = "ARNs of all DynamoDB tables"
  value = [
    aws_dynamodb_table.articles.arn,
    aws_dynamodb_table.article_summaries.arn,
    aws_dynamodb_table.summaries.arn,
    aws_dynamodb_table.pending_approvals.arn,
    aws_dynamodb_table.workflow_runs.arn,
    aws_dynamodb_table.drift_alerts.arn,
    aws_dynamodb_table.oauth_tokens.arn,
    aws_dynamodb_table.evaluations.arn,
    aws_dynamodb_table.summary_stats.arn,
    aws_dynamodb_table.api_call_results.arn,
    aws_dynamodb_table.categories.arn,
    aws_dynamodb_table.tags.arn,
    aws_dynamodb_table.summary_tags.arn,
    aws_dynamodb_table.improvement_suggestions.arn,
  ]
}

output "table_names" {
  description = "Names of all DynamoDB tables"
  value = {
    articles                = aws_dynamodb_table.articles.name
    article_summaries       = aws_dynamodb_table.article_summaries.name
    summaries               = aws_dynamodb_table.summaries.name
    pending_approvals       = aws_dynamodb_table.pending_approvals.name
    workflow_runs           = aws_dynamodb_table.workflow_runs.name
    drift_alerts            = aws_dynamodb_table.drift_alerts.name
    oauth_tokens            = aws_dynamodb_table.oauth_tokens.name
    evaluations             = aws_dynamodb_table.evaluations.name
    summary_stats           = aws_dynamodb_table.summary_stats.name
    api_call_results        = aws_dynamodb_table.api_call_results.name
    categories              = aws_dynamodb_table.categories.name
    tags                    = aws_dynamodb_table.tags.name
    summary_tags            = aws_dynamodb_table.summary_tags.name
    improvement_suggestions = aws_dynamodb_table.improvement_suggestions.name
  }
}
