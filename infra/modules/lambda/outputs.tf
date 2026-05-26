output "function_arns" {
  description = "Map of function name to ARN"
  value       = { for k, v in aws_lambda_function.functions : k => v.arn }
}

output "invoke_arns" {
  description = "Map of function name to invoke ARN"
  value       = { for k, v in aws_lambda_function.functions : k => v.invoke_arn }
}

output "layer_arn" {
  description = "Shared dependencies layer ARN"
  value       = aws_lambda_layer_version.deps.arn
}
