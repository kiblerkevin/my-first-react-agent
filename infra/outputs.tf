output "api_gateway_url" {
  description = "API Gateway endpoint URL"
  value       = module.api_gateway.api_endpoint
}

output "cloudfront_distribution_domain" {
  description = "CloudFront distribution domain name"
  value       = module.cloudfront.distribution_domain_name
}

output "spa_bucket_name" {
  description = "S3 bucket name for SPA assets"
  value       = module.s3_spa.bucket_id
}

output "state_machine_arn" {
  description = "Step Functions state machine ARN"
  value       = module.step_functions.state_machine_arn
}

output "ses_dkim_records" {
  description = "DKIM CNAME records to add in Cloudflare"
  value       = module.ses.dkim_records
}

output "acm_validation_records" {
  description = "ACM DNS validation records to add in Cloudflare"
  value       = module.acm.validation_records
}

output "dynamodb_table_names" {
  description = "DynamoDB table names"
  value       = module.dynamodb.table_names
}
