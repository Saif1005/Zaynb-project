output "compute_environment_arn" {
  description = "Compute environment ARN"
  value       = aws_batch_compute_environment.genomic.arn
}

output "compute_environment_name" {
  description = "Compute environment name"
  value       = aws_batch_compute_environment.genomic.compute_environment_name
}

output "job_queue_arn" {
  description = "Job queue ARN"
  value       = aws_batch_job_queue.genomic.arn
}

output "job_queue_name" {
  description = "Job queue name"
  value       = aws_batch_job_queue.genomic.name
}

output "job_definition_arn" {
  description = "Job definition ARN"
  value       = aws_batch_job_definition.parabricks.arn
}










