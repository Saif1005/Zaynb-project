# Outputs for Genomic Cancer Detection Pipeline

output "vpc_id" {
  description = "VPC ID"
  value       = module.vpc.vpc_id
}

output "vpc_cidr" {
  description = "VPC CIDR block"
  value       = module.vpc.vpc_cidr
}

output "public_subnet_ids" {
  description = "Public subnet IDs"
  value       = module.vpc.public_subnet_ids
}

output "private_subnet_ids" {
  description = "Private subnet IDs"
  value       = module.vpc.private_subnet_ids
}

output "s3_input_bucket_name" {
  description = "Input S3 bucket name"
  value       = module.s3.input_bucket_name
}

output "s3_input_bucket_arn" {
  description = "Input S3 bucket ARN"
  value       = module.s3.input_bucket_arn
}

output "s3_output_bucket_name" {
  description = "Output S3 bucket name"
  value       = module.s3.output_bucket_name
}

output "s3_output_bucket_arn" {
  description = "Output S3 bucket ARN"
  value       = module.s3.output_bucket_arn
}

output "s3_reference_bucket_name" {
  description = "Reference S3 bucket name"
  value       = module.s3.reference_bucket_name
}

output "s3_reference_bucket_arn" {
  description = "Reference S3 bucket ARN"
  value       = module.s3.reference_bucket_arn
}

output "ec2_instance_role_arn" {
  description = "EC2 instance IAM role ARN"
  value       = module.iam.ec2_instance_role_arn
}

output "ec2_instance_role_name" {
  description = "EC2 instance IAM role name"
  value       = module.iam.ec2_instance_role_name
}

output "batch_execution_role_arn" {
  description = "AWS Batch execution role ARN"
  value       = module.iam.batch_execution_role_arn
}

output "security_group_id" {
  description = "EC2 security group ID"
  value       = aws_security_group.ec2_genomic.id
}

output "cloudwatch_log_group" {
  description = "CloudWatch log group name"
  value       = aws_cloudwatch_log_group.genomic_pipeline.name
}

output "batch_job_queue_arn" {
  description = "AWS Batch job queue ARN"
  value       = var.enable_batch ? module.batch[0].job_queue_arn : null
}

output "batch_compute_environment_arn" {
  description = "AWS Batch compute environment ARN"
  value       = var.enable_batch ? module.batch[0].compute_environment_arn : null
}







