output "ec2_instance_role_arn" {
  description = "EC2 instance role ARN"
  value       = aws_iam_role.ec2_instance.arn
}

output "ec2_instance_role_name" {
  description = "EC2 instance role name"
  value       = aws_iam_role.ec2_instance.name
}

output "ec2_instance_profile_name" {
  description = "EC2 instance profile name"
  value       = aws_iam_instance_profile.ec2_instance.name
}

output "batch_execution_role_arn" {
  description = "Batch execution role ARN"
  value       = aws_iam_role.batch_execution.arn
}

output "batch_service_role_arn" {
  description = "Batch service role ARN"
  value       = aws_iam_role.batch_service.arn
}










