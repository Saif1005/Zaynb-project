# Terraform IAM Permission Issues

## Current Limitations

The IAM user `saif-admin` is missing some permissions that Terraform needs. This document explains the workarounds implemented.

## Missing Permissions

1. **S3 Bucket Tagging**
   - Missing: `s3:GetBucketTagging`, `s3:PutBucketTagging`
   - Workaround: Tags have been removed from S3 bucket resources

2. **S3 Bucket Policy**
   - Missing: `s3:GetBucketPolicy`
   - Workaround: Added `lifecycle { ignore_changes = [policy] }` to all S3 buckets
   - If you still get errors, use: `terraform plan -refresh=false` or `terraform apply -refresh=false`

3. **S3 Bucket Deletion**
   - Missing: `s3:DeleteBucket`
   - Workaround: Added `prevent_destroy = true` to all S3 buckets
   - To delete buckets: Remove `prevent_destroy` from lifecycle block, or delete manually via AWS Console

4. **CloudWatch Logs Tagging**
   - Missing: `logs:TagResource`
   - Workaround: Tags removed from CloudWatch log group

5. **CloudWatch Logs Retention Policy**
   - Missing: `logs:PutRetentionPolicy`
   - Workaround: `retention_in_days` removed from CloudWatch log group
   - Retention can be set manually via AWS Console if needed

6. **ECR Push Permissions**
   - Missing: `ecr:InitiateLayerUpload`, `ecr:UploadLayerPart`, `ecr:CompleteLayerUpload`, `ecr:PutImage`
   - Impact: Cannot push Docker images to ECR
   - Workaround: Push images manually from EC2 instance (which has IAM role with ECR permissions), or add ECR permissions to user

## Running Terraform

If you encounter policy read errors, skip the refresh phase:

```bash
# Plan without refresh
terraform plan -refresh=false

# Apply without refresh
terraform apply -refresh=false
```

## Adding Permissions (Future)

To enable full functionality, add these permissions to the `saif-admin` IAM user:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "s3:GetBucketTagging",
        "s3:PutBucketTagging",
        "s3:GetBucketPolicy",
        "s3:DeleteBucket",
        "logs:TagResource",
        "logs:PutRetentionPolicy",
        "ecr:GetAuthorizationToken",
        "ecr:BatchCheckLayerAvailability",
        "ecr:GetDownloadUrlForLayer",
        "ecr:BatchGetImage",
        "ecr:InitiateLayerUpload",
        "ecr:UploadLayerPart",
        "ecr:CompleteLayerUpload",
        "ecr:PutImage"
      ],
      "Resource": "*"
    }
  ]
}
```

Once permissions are added, you can:
1. Uncomment the `default_tags` block in `main.tf`
2. Uncomment tags in S3 bucket resources
3. Uncomment tags in CloudWatch log group
4. Uncomment `retention_in_days` in CloudWatch log group
5. Remove `lifecycle { ignore_changes = [policy] }` blocks
6. Remove `prevent_destroy = true` from S3 bucket lifecycle blocks (if you want Terraform to manage deletion)

