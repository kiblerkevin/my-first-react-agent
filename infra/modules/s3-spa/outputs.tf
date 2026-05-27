output "bucket_id" {
  description = "S3 bucket name"
  value       = aws_s3_bucket.spa.id
}

output "bucket_arn" {
  description = "S3 bucket ARN"
  value       = aws_s3_bucket.spa.arn
}

output "bucket_regional_domain_name" {
  description = "S3 bucket regional domain name"
  value       = aws_s3_bucket.spa.bucket_regional_domain_name
}
