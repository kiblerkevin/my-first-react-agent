resource "aws_apigatewayv2_api" "main" {
  name          = "${var.prefix}-api"
  protocol_type = "HTTP"

  cors_configuration {
    allow_origins = ["https://dashboard.${var.domain}"]
    allow_methods = ["GET", "POST", "OPTIONS"]
    allow_headers = ["Authorization", "Content-Type"]
    max_age       = 3600
  }
}

resource "aws_apigatewayv2_authorizer" "auth0" {
  count            = var.auth0_issuer != "" ? 1 : 0
  api_id           = aws_apigatewayv2_api.main.id
  authorizer_type  = "JWT"
  identity_sources = ["$request.header.Authorization"]
  name             = "${var.prefix}-auth0"

  jwt_configuration {
    audience = [var.auth0_audience]
    issuer   = var.auth0_issuer
  }
}

resource "aws_apigatewayv2_integration" "lambda" {
  api_id                 = aws_apigatewayv2_api.main.id
  integration_type       = "AWS_PROXY"
  integration_uri        = var.api_lambda_invoke_arn
  payload_format_version = "2.0"
}

# Public routes (approval links from email)
resource "aws_apigatewayv2_route" "approve" {
  api_id    = aws_apigatewayv2_api.main.id
  route_key = "GET /approve/{token}"
  target    = "integrations/${aws_apigatewayv2_integration.lambda.id}"
}

resource "aws_apigatewayv2_route" "reject" {
  api_id    = aws_apigatewayv2_api.main.id
  route_key = "POST /reject/{token}"
  target    = "integrations/${aws_apigatewayv2_integration.lambda.id}"
}

resource "aws_apigatewayv2_route" "status" {
  api_id    = aws_apigatewayv2_api.main.id
  route_key = "GET /status/{token}"
  target    = "integrations/${aws_apigatewayv2_integration.lambda.id}"
}

resource "aws_apigatewayv2_route" "health" {
  api_id    = aws_apigatewayv2_api.main.id
  route_key = "GET /health"
  target    = "integrations/${aws_apigatewayv2_integration.lambda.id}"
}

# Authenticated dashboard API routes
resource "aws_apigatewayv2_route" "dashboard_api" {
  api_id             = aws_apigatewayv2_api.main.id
  route_key          = "GET /dashboard/api/{proxy+}"
  target             = "integrations/${aws_apigatewayv2_integration.lambda.id}"
  authorization_type = var.auth0_issuer != "" ? "JWT" : null
  authorizer_id      = var.auth0_issuer != "" ? aws_apigatewayv2_authorizer.auth0[0].id : null
}

resource "aws_apigatewayv2_stage" "default" {
  api_id      = aws_apigatewayv2_api.main.id
  name        = "$default"
  auto_deploy = true
}

# Custom domain (only when cert is issued)
resource "aws_apigatewayv2_domain_name" "api" {
  count       = var.acm_cert_arn != "" ? 1 : 0
  domain_name = "api.${var.domain}"

  domain_name_configuration {
    certificate_arn = var.acm_cert_arn
    endpoint_type   = "REGIONAL"
    security_policy = "TLS_1_2"
  }
}

resource "aws_apigatewayv2_api_mapping" "api" {
  count       = var.acm_cert_arn != "" ? 1 : 0
  api_id      = aws_apigatewayv2_api.main.id
  domain_name = aws_apigatewayv2_domain_name.api[0].id
  stage       = aws_apigatewayv2_stage.default.id
}

# Lambda permission for API Gateway
resource "aws_lambda_permission" "api_gateway" {
  statement_id  = "AllowAPIGatewayInvoke"
  action        = "lambda:InvokeFunction"
  function_name = var.api_lambda_arn
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_apigatewayv2_api.main.execution_arn}/*/*"
}
