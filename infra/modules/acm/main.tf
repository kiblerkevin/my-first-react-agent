terraform {
  required_providers {
    aws = {
      source                = "hashicorp/aws"
      configuration_aliases = [aws, aws.us_east_1]
    }
  }
}

# Certificate for CloudFront (must be us-east-1)
resource "aws_acm_certificate" "cloudfront" {
  provider          = aws.us_east_1
  domain_name       = "dashboard.${var.domain}"
  validation_method = "DNS"

  lifecycle {
    create_before_destroy = true
  }
}

# Certificate for API Gateway (regional, us-west-1)
resource "aws_acm_certificate" "regional" {
  domain_name       = "api.${var.domain}"
  validation_method = "DNS"

  lifecycle {
    create_before_destroy = true
  }
}
