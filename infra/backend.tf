terraform {
  required_version = ">= 1.6.0"

  backend "s3" {
    bucket         = "chicago-sports-recap-tfstate"
    key            = "infra/terraform.tfstate"
    region         = "us-west-1"
    dynamodb_table = "chicago-sports-recap-tflock"
    encrypt        = true
  }
}
