output "distribution_domain_name" {
  description = "CloudFront distribution domain name for Cloudflare CNAME"
  value       = length(aws_cloudfront_distribution.spa) > 0 ? aws_cloudfront_distribution.spa[0].domain_name : ""
}

output "distribution_id" {
  description = "CloudFront distribution ID"
  value       = length(aws_cloudfront_distribution.spa) > 0 ? aws_cloudfront_distribution.spa[0].id : ""
}
