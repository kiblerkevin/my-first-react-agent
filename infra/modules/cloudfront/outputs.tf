output "distribution_domain_name" {
  description = "CloudFront distribution domain name for Cloudflare CNAME"
  value       = aws_cloudfront_distribution.spa.domain_name
}

output "distribution_id" {
  description = "CloudFront distribution ID"
  value       = aws_cloudfront_distribution.spa.id
}
