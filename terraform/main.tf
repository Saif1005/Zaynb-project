# Main Terraform configuration for Genomic Cancer Detection Pipeline

terraform {
  required_version = ">= 1.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }

  # Backend S3 désactivé pour le moment (utiliser backend local)
  # Pour activer le backend S3, décommentez et configurez:
  # backend "s3" {
  #   bucket = "genomic-cancer-pipeline-terraform-state"
  #   key    = "terraform.tfstate"
  #   region = "us-east-1"
  # }
}

provider "aws" {
  region = var.aws_region

  # S3 configuration to handle regional endpoints correctly
  # Note: S3 buckets are global but operations must use correct regional endpoint
  s3_use_path_style = false
  skip_region_validation = false

  # Default tags disabled due to missing tagging permissions
  # Uncomment when IAM user has s3:GetBucketTagging, s3:PutBucketTagging, and logs:TagResource permissions
  # default_tags {
  #   tags = {
  #     Project     = "GenomicCancerDetection"
  #     ManagedBy   = "Terraform"
  #     Environment = var.environment
  #   }
  # }
}

# Additional provider for S3 operations if needed for cross-region access
# Uncomment if buckets exist in a different region
# provider "aws" {
#   alias  = "s3"
#   region = "us-east-1"  # Change to the region where buckets actually exist
# }

# Data sources
data "aws_caller_identity" "current" {}
data "aws_region" "current" {}

# VPC Module
module "vpc" {
  source = "./modules/vpc"

  environment = var.environment
  vpc_cidr    = var.vpc_cidr
  region      = var.aws_region
}

# S3 Module
module "s3" {
  source = "./modules/s3"

  environment           = var.environment
  input_bucket_name     = var.s3_input_bucket_name
  output_bucket_name    = var.s3_output_bucket_name
  reference_bucket_name = var.s3_reference_bucket_name
  region                = var.aws_region
}

# IAM Module
module "iam" {
  source = "./modules/iam"

  environment = var.environment
  account_id  = data.aws_caller_identity.current.account_id
  region      = var.aws_region

  s3_input_bucket_arn     = module.s3.input_bucket_arn
  s3_output_bucket_arn    = module.s3.output_bucket_arn
  s3_reference_bucket_arn = module.s3.reference_bucket_arn
}

# EC2 Security Group
resource "aws_security_group" "ec2_genomic" {
  name        = "${var.environment}-genomic-ec2-sg"
  description = "Security group for genomic processing EC2 instances"
  vpc_id      = module.vpc.vpc_id

  ingress {
    description = "SSH from anywhere (restrict in production)"
    from_port   = 22
    to_port     = 22
    protocol    = "tcp"
    cidr_blocks = var.environment == "prod" ? var.allowed_ssh_cidrs : ["0.0.0.0/0"]
  }

  egress {
    description = "Allow all outbound traffic"
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    Name = "${var.environment}-genomic-ec2-sg"
  }
}

# CloudWatch Log Group
resource "aws_cloudwatch_log_group" "genomic_pipeline" {
  name = var.cloudwatch_log_group
  
  # Retention policy removed due to missing logs:PutRetentionPolicy permission
  # retention_in_days = var.log_retention_days

  # Tags removed due to missing logs:TagResource permission
  # tags = {
  #   Name = "${var.environment}-genomic-pipeline-logs"
  # }
}

# AWS Batch Module (optional, for batch processing)
module "batch" {
  source = "./modules/batch"

  environment           = var.environment
  vpc_id                = module.vpc.vpc_id
  subnet_ids            = module.vpc.private_subnet_ids
  security_group_ids    = [aws_security_group.ec2_genomic.id]
  instance_role_arn     = module.iam.ec2_instance_role_arn
  execution_role_arn    = module.iam.batch_execution_role_arn
  batch_service_role_arn = module.iam.batch_service_role_arn
  instance_type         = var.ec2_instance_type
  max_vcpus             = var.batch_max_vcpus
  min_vcpus             = var.batch_min_vcpus
  desired_vcpus         = var.batch_desired_vcpus

  count = var.enable_batch ? 1 : 0
}

# API Module (ECS Fargate) - Désactivé pour le moment (nécessite Load Balancer support)
# Le compte AWS ne supporte pas encore les Load Balancers
# module "api" {
#   source = "./modules/api"
#   ...
#   count = 0  # Désactivé
# }

