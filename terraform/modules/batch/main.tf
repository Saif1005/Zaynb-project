# AWS Batch Module for Genomic Pipeline

# Compute Environment
resource "aws_batch_compute_environment" "genomic" {
  compute_environment_name = "${var.environment}-genomic-compute"
  type                     = "MANAGED"
  state                    = "ENABLED"
  service_role             = var.batch_service_role_arn != null ? var.batch_service_role_arn : aws_iam_role.batch_service[0].arn

  compute_resources {
    type                = "EC2"
    instance_role       = var.instance_role_arn
    instance_type       = toset([var.instance_type])  # Set of strings required
    max_vcpus           = var.max_vcpus
    min_vcpus           = var.min_vcpus
    desired_vcpus       = var.desired_vcpus
    subnets             = var.subnet_ids
    security_group_ids  = var.security_group_ids
    allocation_strategy = "BEST_FIT_PROGRESSIVE"

    tags = {
      Name        = "${var.environment}-genomic-batch-compute"
      Environment = var.environment
    }
  }

  depends_on = [aws_iam_role_policy_attachment.batch_service]
}

# Job Queue - ✅ CORRIGÉ
resource "aws_batch_job_queue" "genomic" {
  name     = "${var.environment}-genomic-queue"
  state    = "ENABLED"
  priority = 1
  
  compute_environment_order {
    order               = 1
    compute_environment = aws_batch_compute_environment.genomic.arn
  }
}

# Job Definition (example for Parabricks)
resource "aws_batch_job_definition" "parabricks" {
  name = "${var.environment}-parabricks-job"
  type = "container"

  container_properties = jsonencode({
    image      = "nvcr.io/nvidia/clara/clara-parabricks:4.6.0-1"
    vcpus      = 8
    memory     = 61440
    privileged = true
    jobRoleArn = var.instance_role_arn

    environment = [
      {
        name  = "PARABRICKS_LICENSE_KEY"
        value = var.parabricks_license_key
      }
    ]

    resourceRequirements = [
      {
        type  = "GPU"
        value = "1"
      }
    ]

    mountPoints = []
    volumes     = []
  })
}

# Batch Service Role (if not provided)
resource "aws_iam_role" "batch_service" {
  count = var.batch_service_role_arn == null ? 1 : 0
  name  = "${var.environment}-genomic-batch-service-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "batch.amazonaws.com"
        }
      }
    ]
  })
}

resource "aws_iam_role_policy_attachment" "batch_service" {
  count      = var.batch_service_role_arn == null ? 1 : 0
  role       = aws_iam_role.batch_service[0].name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSBatchServiceRole"
}