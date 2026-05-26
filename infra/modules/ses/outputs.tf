output "domain_identity_arn" {
  description = "ARN of the SES domain identity"
  value       = aws_ses_domain_identity.main.arn
}

output "dkim_records" {
  description = "DKIM CNAME records to add in Cloudflare"
  value = [
    for token in aws_ses_domain_dkim.main.dkim_tokens : {
      name  = "${token}._domainkey.${var.domain}"
      value = "${token}.dkim.amazonses.com"
    }
  ]
}

output "verification_token" {
  description = "TXT record value for domain verification"
  value       = aws_ses_domain_identity.main.verification_token
}
