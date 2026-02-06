# Variables for Genomic Cancer Detection Pipeline

variable "aws_region" {
  description = "AWS region"
  type        = string
  default     = "us-east-1"
}

variable "environment" {
  description = "Environment name (dev, prod)"
  type        = string
  validation {
    condition     = contains(["dev", "prod"], var.environment)
    error_message = "Environment must be 'dev' or 'prod'."
  }
}

variable "vpc_cidr" {
  description = "CIDR block for VPC"
  type        = string
  default     = "10.0.0.0/16"
}

variable "s3_input_bucket_name" {
  description = "Name for input S3 bucket"
  type        = string
  default     = "genomic-cancer-pipeline-input"
}

variable "s3_output_bucket_name" {
  description = "Name for output S3 bucket"
  type        = string
  default     = "genomic-cancer-pipeline-output"
}

variable "s3_reference_bucket_name" {
  description = "Name for reference S3 bucket"
  type        = string
  default     = "genomic-references"
}

variable "ec2_instance_type" {
  description = "EC2 instance type for GPU processing"
  type        = string
  default     = "p3.2xlarge"
}

variable "cloudwatch_log_group" {
  description = "CloudWatch log group name"
  type        = string
  default     = "genomic-cancer-pipeline"
}

variable "log_retention_days" {
  description = "CloudWatch log retention in days"
  type        = number
  default     = 30
}

variable "allowed_ssh_cidrs" {
  description = "CIDR blocks allowed for SSH access (production)"
  type        = list(string)
  default     = []
}

variable "enable_batch" {
  description = "Enable AWS Batch compute environment"
  type        = bool
  default     = false
}

variable "batch_max_vcpus" {
  description = "Maximum vCPUs for AWS Batch"
  type        = number
  default     = 256
}

variable "batch_min_vcpus" {
  description = "Minimum vCPUs for AWS Batch"
  type        = number
  default     = 0
}

variable "batch_desired_vcpus" {
  description = "Desired vCPUs for AWS Batch"
  type        = number
  default     = 0
}

variable "api_image_uri" {
  description = "Docker image URI for API"
  type        = string
  default     = ""
}variable "agent_image_uri" {
  description = "Docker image URI for agents"
  type        = string
  default     = ""
}variable "instance_id" {
  description = "EC2 instance ID for Parabricks"
  type        = string
  default     = ""
}
