variable "environment" {
  description = "Environment name"
  type        = string
}

variable "account_id" {
  description = "AWS account ID"
  type        = string
}

variable "region" {
  description = "AWS region"
  type        = string
}

variable "s3_input_bucket_arn" {
  description = "Input S3 bucket ARN"
  type        = string
}

variable "s3_output_bucket_arn" {
  description = "Output S3 bucket ARN"
  type        = string
}

variable "s3_reference_bucket_arn" {
  description = "Reference S3 bucket ARN"
  type        = string
}

