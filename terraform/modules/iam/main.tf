# IAM Module for Genomic Pipeline

# EC2 Instance Role
resource "aws_iam_role" "ec2_instance" {
  name = "${var.environment}-genomic-ec2-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "ec2.amazonaws.com"
        }
      }
    ]
  })

  tags = {
    Name = "${var.environment}-genomic-ec2-role"
  }
}

# EC2 Instance Profile
resource "aws_iam_instance_profile" "ec2_instance" {
  name = "${var.environment}-genomic-ec2-profile"
  role = aws_iam_role.ec2_instance.name
}

# EC2 Instance Policy (S3 access)
resource "aws_iam_role_policy" "ec2_s3_access" {
  name = "${var.environment}-genomic-ec2-s3-policy"
  role = aws_iam_role.ec2_instance.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "s3:GetObject",
          "s3:PutObject",
          "s3:DeleteObject",
          "s3:ListBucket"
        ]
        Resource = [
          "${var.s3_input_bucket_arn}",
          "${var.s3_input_bucket_arn}/*",
          "${var.s3_output_bucket_arn}",
          "${var.s3_output_bucket_arn}/*",
          "${var.s3_reference_bucket_arn}",
          "${var.s3_reference_bucket_arn}/*"
        ]
      }
    ]
  })
}

# EC2 CloudWatch Logs Policy
resource "aws_iam_role_policy" "ec2_cloudwatch" {
  name = "${var.environment}-genomic-ec2-cloudwatch-policy"
  role = aws_iam_role.ec2_instance.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "logs:CreateLogGroup",
          "logs:CreateLogStream",
          "logs:PutLogEvents",
          "logs:DescribeLogStreams"
        ]
        Resource = "arn:aws:logs:${var.region}:${var.account_id}:log-group:*"
      }
    ]
  })
}

# EC2 ECR Policy (for pushing Docker images)
resource "aws_iam_role_policy" "ec2_ecr_access" {
  name = "${var.environment}-genomic-ec2-ecr-policy"
  role = aws_iam_role.ec2_instance.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "ecr:GetAuthorizationToken"
        ]
        Resource = "*"
      },
      {
        Effect = "Allow"
        Action = [
          "ecr:BatchCheckLayerAvailability",
          "ecr:GetDownloadUrlForLayer",
          "ecr:BatchGetImage",
          "ecr:InitiateLayerUpload",
          "ecr:UploadLayerPart",
          "ecr:CompleteLayerUpload",
          "ecr:PutImage"
        ]
        Resource = [
          "arn:aws:ecr:${var.region}:${var.account_id}:repository/genomic-api",
          "arn:aws:ecr:${var.region}:${var.account_id}:repository/genomic-agent"
        ]
      }
    ]
  })
}

# AWS Batch Execution Role
resource "aws_iam_role" "batch_execution" {
  name = "${var.environment}-genomic-batch-execution-role"

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

  tags = {
    Name = "${var.environment}-genomic-batch-execution-role"
  }
}

# Batch Execution Policy (ECR, S3, CloudWatch)
resource "aws_iam_role_policy" "batch_execution" {
  name = "${var.environment}-genomic-batch-execution-policy"
  role = aws_iam_role.batch_execution.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "ecr:GetAuthorizationToken",
          "ecr:BatchCheckLayerAvailability",
          "ecr:GetDownloadUrlForLayer",
          "ecr:BatchGetImage"
        ]
        Resource = "*"
      },
      {
        Effect = "Allow"
        Action = [
          "s3:GetObject",
          "s3:PutObject",
          "s3:ListBucket"
        ]
        Resource = [
          "${var.s3_input_bucket_arn}",
          "${var.s3_input_bucket_arn}/*",
          "${var.s3_output_bucket_arn}",
          "${var.s3_output_bucket_arn}/*",
          "${var.s3_reference_bucket_arn}",
          "${var.s3_reference_bucket_arn}/*"
        ]
      },
      {
        Effect = "Allow"
        Action = [
          "logs:CreateLogGroup",
          "logs:CreateLogStream",
          "logs:PutLogEvents"
        ]
        Resource = "arn:aws:logs:${var.region}:${var.account_id}:log-group:*"
      }
    ]
  })
}

# AWS Batch Service Role
resource "aws_iam_role" "batch_service" {
  name = "${var.environment}-genomic-batch-service-role"

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

  tags = {
    Name = "${var.environment}-genomic-batch-service-role"
  }
}

# Attach AWS managed policy for Batch service role
resource "aws_iam_role_policy_attachment" "batch_service" {
  role       = aws_iam_role.batch_service.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSBatchServiceRole"
}


