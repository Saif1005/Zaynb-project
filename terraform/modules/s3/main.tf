# S3 Module for Genomic Pipeline

# Input Bucket
resource "aws_s3_bucket" "input" {
  bucket = "${var.input_bucket_name}-${var.environment}-${data.aws_caller_identity.current.account_id}"

  # Tags removed due to missing s3:GetBucketTagging/s3:PutBucketTagging permissions
  # tags = {
  #   Name        = "${var.environment}-genomic-input"
  #   Environment = var.environment
  # }

  # Ignore policy-related attributes due to missing s3:GetBucketPolicy permission
  # Note: If you still get policy read errors, use: terraform plan -refresh=false
  lifecycle {
    ignore_changes = [policy]
    # Prevent accidental deletion due to missing s3:DeleteBucket permission
    # To delete buckets, remove this line or manually delete via AWS Console
    prevent_destroy = true
  }
}

resource "aws_s3_bucket_versioning" "input" {
  bucket = aws_s3_bucket.input.id

  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "input" {
  bucket = aws_s3_bucket.input.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

resource "aws_s3_bucket_public_access_block" "input" {
  bucket = aws_s3_bucket.input.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets  = true
}

# Output Bucket
resource "aws_s3_bucket" "output" {
  bucket = "${var.output_bucket_name}-${var.environment}-${data.aws_caller_identity.current.account_id}"

  # Tags removed due to missing s3:GetBucketTagging/s3:PutBucketTagging permissions
  # tags = {
  #   Name        = "${var.environment}-genomic-output"
  #   Environment = var.environment
  # }

  # Ignore policy-related attributes due to missing s3:GetBucketPolicy permission
  # Note: If you still get policy read errors, use: terraform plan -refresh=false
  lifecycle {
    ignore_changes = [policy]
    # Prevent accidental deletion due to missing s3:DeleteBucket permission
    # To delete buckets, remove this line or manually delete via AWS Console
    prevent_destroy = true
  }
}

resource "aws_s3_bucket_versioning" "output" {
  bucket = aws_s3_bucket.output.id

  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "output" {
  bucket = aws_s3_bucket.output.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

resource "aws_s3_bucket_public_access_block" "output" {
  bucket = aws_s3_bucket.output.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets  = true
}

# Reference Bucket
resource "aws_s3_bucket" "reference" {
  bucket = "${var.reference_bucket_name}-${var.environment}-${data.aws_caller_identity.current.account_id}"

  # Tags removed due to missing s3:GetBucketTagging/s3:PutBucketTagging permissions
  # tags = {
  #   Name        = "${var.environment}-genomic-reference"
  #   Environment = var.environment
  # }

  # Ignore policy-related attributes due to missing s3:GetBucketPolicy permission
  # Note: If you still get policy read errors, use: terraform plan -refresh=false
  lifecycle {
    ignore_changes = [policy]
    # Prevent accidental deletion due to missing s3:DeleteBucket permission
    # To delete buckets, remove this line or manually delete via AWS Console
    prevent_destroy = true
  }
}

resource "aws_s3_bucket_versioning" "reference" {
  bucket = aws_s3_bucket.reference.id

  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "reference" {
  bucket = aws_s3_bucket.reference.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

resource "aws_s3_bucket_public_access_block" "reference" {
  bucket = aws_s3_bucket.reference.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets  = true
}

# Lifecycle policies for cost optimization
resource "aws_s3_bucket_lifecycle_configuration" "input" {
  bucket = aws_s3_bucket.input.id

  rule {
    id     = "delete-old-inputs"
    status = "Enabled"

    filter {
      prefix = ""  # Apply to all objects
    }

    expiration {
      days = 90  # Delete input files after 90 days
    }
  }
}

resource "aws_s3_bucket_lifecycle_configuration" "output" {
  bucket = aws_s3_bucket.output.id

  rule {
    id     = "transition-to-glacier"
    status = "Enabled"

    filter {
      prefix = ""  # Apply to all objects
    }

    transition {
      days          = 30
      storage_class = "GLACIER"
    }

    transition {
      days          = 120  # Must be at least 90 days after GLACIER (30 + 90 = 120)
      storage_class = "DEEP_ARCHIVE"
    }
  }
}

# Data source
data "aws_caller_identity" "current" {}


