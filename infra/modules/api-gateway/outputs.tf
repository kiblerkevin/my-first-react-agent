output "api_endpoint" {
  description = "API Gateway endpoint URL"
  value       = aws_apigatewayv2_api.main.api_endpoint
}

output "api_id" {
  description = "API Gateway ID"
  value       = aws_apigatewayv2_api.main.id
}

output "custom_domain_target" {
  description = "Target domain name for Cloudflare CNAME"
  value       = aws_apigatewayv2_domain_name.api.domain_name_configuration[0].target_domain_name
}
