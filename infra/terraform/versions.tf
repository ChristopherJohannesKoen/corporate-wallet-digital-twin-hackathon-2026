terraform {
  required_version = ">= 1.8.0"

  backend "s3" {}

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "6.55.0"
    }
  }
}

provider "aws" {
  region = var.aws_region

  default_tags {
    tags = {
      Application        = "corporate-wallet-digital-twin"
      Environment        = var.environment
      DataClassification = "confidential"
      ManagedBy          = "terraform"
    }
  }
}
