variable "environment" {
  description = "Environment name"
  type        = string
}

variable "vpc_id" {
  description = "VPC ID"
  type        = string
}

variable "subnet_ids" {
  description = "Subnet IDs for compute environment"
  type        = list(string)
}

variable "security_group_ids" {
  description = "Security group IDs"
  type        = list(string)
}

variable "instance_role_arn" {
  description = "EC2 instance role ARN"
  type        = string
}

variable "execution_role_arn" {
  description = "Batch execution role ARN"
  type        = string
}

variable "instance_type" {
  description = "EC2 instance type"
  type        = string
  default     = "p3.2xlarge"
}

variable "max_vcpus" {
  description = "Maximum vCPUs"
  type        = number
  default     = 256
}

variable "min_vcpus" {
  description = "Minimum vCPUs"
  type        = number
  default     = 0
}

variable "desired_vcpus" {
  description = "Desired vCPUs"
  type        = number
  default     = 0
}

variable "parabricks_license_key" {
  description = "Parabricks license key"
  type        = string
  default     = ""
  sensitive   = true
}

variable "batch_service_role_arn" {
  description = "Batch service role ARN (optional)"
  type        = string
  default     = null
}










