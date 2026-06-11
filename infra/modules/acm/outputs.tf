output "cloudfront_cert_arn" {
  description = "ACM certificate ARN for CloudFront (us-east-1), empty if not yet validated"
  value       = var.wait_for_validation ? aws_acm_certificate.cloudfront.arn : ""
}

output "regional_cert_arn" {
  description = "ACM certificate ARN for API Gateway (regional), empty if not yet validated"
  value       = var.wait_for_validation ? aws_acm_certificate.regional.arn : ""
}

output "validation_records" {
  description = "DNS validation CNAME records to add in Cloudflare"
  value = concat(
    [for dvo in aws_acm_certificate.cloudfront.domain_validation_options : {
      name  = dvo.resource_record_name
      type  = dvo.resource_record_type
      value = dvo.resource_record_value
    }],
    [for dvo in aws_acm_certificate.regional.domain_validation_options : {
      name  = dvo.resource_record_name
      type  = dvo.resource_record_type
      value = dvo.resource_record_value
    }]
  )
}
