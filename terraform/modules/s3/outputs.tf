output "input_bucket_name" {
  description = "Input bucket name"
  value       = aws_s3_bucket.input.id
}

output "input_bucket_arn" {
  description = "Input bucket ARN"
  value       = aws_s3_bucket.input.arn
}

output "output_bucket_name" {
  description = "Output bucket name"
  value       = aws_s3_bucket.output.id
}

output "output_bucket_arn" {
  description = "Output bucket ARN"
  value       = aws_s3_bucket.output.arn
}

output "reference_bucket_name" {
  description = "Reference bucket name"
  value       = aws_s3_bucket.reference.id
}

output "reference_bucket_arn" {
  description = "Reference bucket ARN"
  value       = aws_s3_bucket.reference.arn
}


