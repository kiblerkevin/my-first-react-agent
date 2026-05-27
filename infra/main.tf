locals {
  prefix = "${var.project}-${var.environment}"
}

module "dynamodb" {
  source = "./modules/dynamodb"

  prefix              = local.prefix
  deletion_protection = var.dynamodb_deletion_protection
}

module "secrets_manager" {
  source = "./modules/secrets-manager"

  prefix = local.prefix
}

module "ses" {
  source = "./modules/ses"

  domain = var.domain
  prefix = local.prefix
}

module "acm" {
  source = "./modules/acm"

  domain     = var.domain
  prefix     = local.prefix
  aws_region = var.aws_region

  providers = {
    aws           = aws
    aws.us_east_1 = aws.us_east_1
  }
}

module "iam" {
  source = "./modules/iam"

  prefix              = local.prefix
  aws_region          = var.aws_region
  dynamodb_table_arns = module.dynamodb.table_arns
  secret_arn          = module.secrets_manager.secret_arn
  ses_domain_arn      = module.ses.domain_identity_arn
}

module "lambda" {
  source = "./modules/lambda"

  prefix             = local.prefix
  aws_region         = var.aws_region
  execution_role_arn = module.iam.lambda_execution_role_arn
  secret_arn         = module.secrets_manager.secret_arn
  log_retention_days = var.lambda_log_retention_days
  environment_variables = {
    ENVIRONMENT  = var.environment
    SECRET_ARN   = module.secrets_manager.secret_arn
    TABLE_PREFIX = local.prefix
  }
}

module "step_functions" {
  source = "./modules/step-functions"

  prefix      = local.prefix
  lambda_arns = module.lambda.function_arns
}

module "eventbridge" {
  source = "./modules/eventbridge"

  prefix            = local.prefix
  enabled           = var.eventbridge_enabled
  state_machine_arn = module.step_functions.state_machine_arn
}

module "api_gateway" {
  source = "./modules/api-gateway"

  prefix                = local.prefix
  api_lambda_arn        = module.lambda.function_arns["api-handler"]
  api_lambda_invoke_arn = module.lambda.invoke_arns["api-handler"]
  auth0_issuer          = var.auth0_issuer
  auth0_audience        = var.auth0_audience
  domain                = var.domain
  acm_cert_arn          = module.acm.regional_cert_arn
}

module "s3_spa" {
  source = "./modules/s3-spa"

  prefix = local.prefix
}

module "waf" {
  source = "./modules/waf"

  prefix = local.prefix

  providers = {
    aws = aws.us_east_1
  }
}

module "cloudfront" {
  source = "./modules/cloudfront"

  prefix                          = local.prefix
  domain                          = var.domain
  spa_bucket_id                   = module.s3_spa.bucket_id
  spa_bucket_arn                  = module.s3_spa.bucket_arn
  spa_bucket_regional_domain_name = module.s3_spa.bucket_regional_domain_name
  acm_cert_arn                    = module.acm.cloudfront_cert_arn
  waf_web_acl_arn                 = module.waf.web_acl_arn
}
