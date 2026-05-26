resource "aws_secretsmanager_secret" "app_secrets" {
  name                    = "${var.prefix}-secrets"
  recovery_window_in_days = 7
}

resource "aws_secretsmanager_secret_version" "initial" {
  secret_id = aws_secretsmanager_secret.app_secrets.id
  secret_string = jsonencode({
    NEWSAPI_KEY         = ""
    SERPAPI_KEY         = ""
    LANGFUSE_PUBLIC_KEY = ""
    LANGFUSE_SECRET_KEY = ""
    LANGFUSE_HOST       = ""
    WORDPRESS_SITE_URL  = ""
    WORDPRESS_USERNAME  = ""
    WORDPRESS_PASSWORD  = ""
    AUTH0_CLIENT_ID     = ""
    AUTH0_CLIENT_SECRET = ""
  })

  lifecycle {
    ignore_changes = [secret_string]
  }
}
