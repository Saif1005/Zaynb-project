variable "environment" {
  description = "Environment name"
  type        = string
}

variable "input_bucket_name" {
  description = "Input bucket name prefix"
  type        = string
}

variable "output_bucket_name" {
  description = "Output bucket name prefix"
  type        = string
}

variable "reference_bucket_name" {
  description = "Reference bucket name prefix"
  type        = string
}

variable "region" {
  description = "AWS region"
  type        = string
}


