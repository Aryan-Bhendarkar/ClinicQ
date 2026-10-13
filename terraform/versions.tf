terraform {
  required_version = ">= 1.5.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }

  # Local state keeps the capstone self-contained. For team use, move this to an
  # S3 bucket with DynamoDB locking (see README).
}

provider "aws" {
  region = var.aws_region

  default_tags {
    tags = {
      Project     = "clinicq"
      Environment = var.environment
      ManagedBy   = "terraform"
    }
  }
}
