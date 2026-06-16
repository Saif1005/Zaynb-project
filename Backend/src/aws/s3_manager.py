"""S3 manager module for uploading/downloading genomic data files."""

from pathlib import Path
from typing import Optional, List
from botocore.exceptions import ClientError
import boto3
from loguru import logger

from config.aws_config import aws_config


class S3ManagerError(Exception):
    """Custom exception for S3 operations."""

    pass


class S3Manager:
    """Manager for S3 operations (upload, download, list)."""

    def __init__(
        self,
        bucket_name: Optional[str] = None,
        region: Optional[str] = None,
    ):
        """
        Initialize S3 manager.

        Args:
            bucket_name: Optional S3 bucket name (defaults to config)
            region: Optional AWS region (defaults to config)
        """
        self.bucket_name = bucket_name or aws_config.s3_bucket_name
        self.region = region or aws_config.region

        # Initialize S3 client
        try:
            self.s3_client = boto3.client("s3", region_name=self.region)
            logger.info(f"S3 client initialized for bucket: {self.bucket_name}")
        except Exception as e:
            logger.error(f"Failed to initialize S3 client: {e}")
            raise S3ManagerError(f"S3 initialization failed: {e}") from e

    def upload_file(
        self,
        local_path: str,
        s3_key: str,
        bucket_name: Optional[str] = None,
        show_progress: bool = True,
    ) -> str:
        """
        Upload a file to S3.

        Args:
            local_path: Local file path
            s3_key: S3 object key (path in bucket)
            bucket_name: Optional bucket name override
            show_progress: Show upload progress bar

        Returns:
            S3 URI of uploaded file

        Raises:
            S3ManagerError: If upload fails
        """
        bucket = bucket_name or self.bucket_name
        local_file = Path(local_path)

        if not local_file.exists():
            raise S3ManagerError(f"Local file not found: {local_path}")

        try:
            file_size = local_file.stat().st_size
            logger.info(
                f"Uploading {local_path} ({file_size / (1024**2):.2f} MB) "
                f"to s3://{bucket}/{s3_key}"
            )

            # Use multipart upload for large files (>100MB)
            if file_size > 100 * 1024 * 1024:
                self._upload_multipart(local_path, s3_key, bucket, show_progress)
            else:
                self._upload_simple(local_path, s3_key, bucket, show_progress)

            s3_uri = f"s3://{bucket}/{s3_key}"
            logger.info(f"Successfully uploaded to {s3_uri}")
            return s3_uri

        except ClientError as e:
            error_code = e.response.get("Error", {}).get("Code", "")
            error_message = str(e)
            
            if error_code == "403" or "Forbidden" in error_message:
                error_msg = (
                    f"Access denied (403 Forbidden) when uploading to: s3://{bucket}/{s3_key}\n"
                    "This indicates a permissions issue. Please check:\n"
                    "  1. Your AWS credentials have S3 write permissions\n"
                    "  2. The IAM policy includes 's3:PutObject' and 's3:PutObjectAcl' permissions\n"
                    "  3. The bucket policy allows write access from your AWS account\n"
                    f"Bucket: {bucket}\n"
                    f"Key: {s3_key}\n"
                    "To fix this:\n"
                    "  - Verify your AWS credentials: aws sts get-caller-identity\n"
                    "  - Check IAM permissions for S3 write access\n"
                    "  - Verify bucket policy allows your account/role to write"
                )
            elif error_code == "AccessDenied":
                error_msg = (
                    f"Access denied when uploading to: s3://{bucket}/{s3_key}\n"
                    "Please verify your AWS credentials and S3 write permissions."
                )
            else:
                error_msg = f"Failed to upload {local_path} to S3: {e}\nError Code: {error_code}"
            
            logger.error(error_msg)
            raise S3ManagerError(error_msg) from e
        except Exception as e:
            error_msg = f"Unexpected error uploading to S3: {e}"
            logger.error(error_msg)
            raise S3ManagerError(error_msg) from e

    def _upload_simple(
        self, local_path: str, s3_key: str, bucket: str, show_progress: bool
    ) -> None:
        """Simple upload for small files."""
        self.s3_client.upload_file(local_path, bucket, s3_key)

    def _upload_multipart(
        self, local_path: str, s3_key: str, bucket: str, show_progress: bool
    ) -> None:
        """Multipart upload for large files."""
        # Use TransferConfig for multipart uploads
        from boto3.s3.transfer import TransferConfig

        config = TransferConfig(
            multipart_threshold=100 * 1024 * 1024,  # 100MB
            max_concurrency=10,
            multipart_chunksize=10 * 1024 * 1024,  # 10MB chunks
        )

        self.s3_client.upload_file(
            local_path, bucket, s3_key, Config=config
        )

    def download_file(
        self,
        s3_key: str,
        local_path: str,
        bucket_name: Optional[str] = None,
        show_progress: bool = True,
    ) -> str:
        """
        Download a file from S3.

        Args:
            s3_key: S3 object key (path in bucket)
            local_path: Local file path to save to
            bucket_name: Optional bucket name override
            show_progress: Show download progress bar

        Returns:
            Path to downloaded file

        Raises:
            S3ManagerError: If download fails
        """
        bucket = bucket_name or self.bucket_name
        local_file = Path(local_path)

        # Create parent directory if needed
        local_file.parent.mkdir(parents=True, exist_ok=True)

        try:
            logger.info(
                f"Downloading s3://{bucket}/{s3_key} to {local_path}"
            )

            # Get object size for progress bar
            if show_progress:
                try:
                    response = self.s3_client.head_object(
                        Bucket=bucket, Key=s3_key
                    )
                    file_size = response["ContentLength"]
                except Exception:
                    file_size = None
            else:
                file_size = None

            self.s3_client.download_file(bucket, s3_key, local_path)

            if local_file.exists():
                logger.info(
                    f"Successfully downloaded {local_path} "
                    f"({local_file.stat().st_size / (1024**2):.2f} MB)"
                )
            return str(local_file)

        except ClientError as e:
            error_code = e.response.get("Error", {}).get("Code", "")
            error_message = str(e)
            
            if error_code == "404":
                error_msg = (
                    f"S3 object not found: s3://{bucket}/{s3_key}\n"
                    "Please verify:\n"
                    "  1. The file path is correct\n"
                    "  2. The file exists in the bucket\n"
                    "  3. The bucket name is correct"
                )
            elif error_code == "403" or "Forbidden" in error_message:
                error_msg = (
                    f"Access denied (403 Forbidden) when accessing: s3://{bucket}/{s3_key}\n"
                    "This indicates a permissions issue. Please check:\n"
                    "  1. Your AWS credentials have S3 read permissions\n"
                    "  2. The IAM policy includes 's3:GetObject' and 's3:ListBucket' permissions\n"
                    "  3. The bucket policy allows access from your AWS account\n"
                    "  4. The object exists and is accessible\n"
                    f"Bucket: {bucket}\n"
                    f"Key: {s3_key}\n"
                    "To fix this:\n"
                    "  - Verify your AWS credentials: aws sts get-caller-identity\n"
                    "  - Check IAM permissions for S3 access\n"
                    "  - Verify bucket policy allows your account/role"
                )
            elif error_code == "AccessDenied":
                error_msg = (
                    f"Access denied when accessing: s3://{bucket}/{s3_key}\n"
                    "Please verify your AWS credentials and S3 permissions."
                )
            else:
                error_msg = f"Failed to download from S3: {e}\nError Code: {error_code}"
            
            logger.error(error_msg)
            raise S3ManagerError(error_msg) from e
        except Exception as e:
            error_msg = f"Unexpected error downloading from S3: {e}"
            logger.error(error_msg)
            raise S3ManagerError(error_msg) from e

    def list_files(
        self,
        prefix: str = "",
        bucket_name: Optional[str] = None,
        max_keys: int = 1000,
    ) -> List[str]:
        """
        List files in S3 bucket with given prefix.

        Args:
            prefix: S3 key prefix to filter
            bucket_name: Optional bucket name override
            max_keys: Maximum number of keys to return

        Returns:
            List of S3 keys

        Raises:
            S3ManagerError: If listing fails
        """
        bucket = bucket_name or self.bucket_name
        keys = []

        try:
            paginator = self.s3_client.get_paginator("list_objects_v2")
            pages = paginator.paginate(
                Bucket=bucket, Prefix=prefix, MaxKeys=max_keys
            )

            for page in pages:
                if "Contents" in page:
                    for obj in page["Contents"]:
                        keys.append(obj["Key"])

            logger.debug(f"Listed {len(keys)} files with prefix: {prefix}")
            return keys

        except ClientError as e:
            error_msg = f"Failed to list S3 objects: {e}"
            logger.error(error_msg)
            raise S3ManagerError(error_msg) from e

    def file_exists(
        self, s3_key: str, bucket_name: Optional[str] = None
    ) -> bool:
        """
        Check if a file exists in S3.

        Args:
            s3_key: S3 object key
            bucket_name: Optional bucket name override

        Returns:
            True if file exists, False otherwise
        """
        bucket = bucket_name or self.bucket_name

        try:
            self.s3_client.head_object(Bucket=bucket, Key=s3_key)
            return True
        except ClientError as e:
            error_code = e.response.get("Error", {}).get("Code", "")
            if error_code == "404":
                return False
            # Re-raise other errors
            raise S3ManagerError(f"Error checking S3 file existence: {e}") from e

    def delete_file(
        self, s3_key: str, bucket_name: Optional[str] = None
    ) -> None:
        """
        Delete a file from S3.

        Args:
            s3_key: S3 object key
            bucket_name: Optional bucket name override

        Raises:
            S3ManagerError: If deletion fails
        """
        bucket = bucket_name or self.bucket_name

        try:
            self.s3_client.delete_object(Bucket=bucket, Key=s3_key)
            logger.info(f"Deleted s3://{bucket}/{s3_key}")
        except ClientError as e:
            error_msg = f"Failed to delete S3 file: {e}"
            logger.error(error_msg)
            raise S3ManagerError(error_msg) from e

    def get_file_size(
        self, s3_key: str, bucket_name: Optional[str] = None
    ) -> int:
        """
        Get file size in bytes from S3.

        Args:
            s3_key: S3 object key
            bucket_name: Optional bucket name override

        Returns:
            File size in bytes

        Raises:
            S3ManagerError: If operation fails
        """
        bucket = bucket_name or self.bucket_name

        try:
            response = self.s3_client.head_object(Bucket=bucket, Key=s3_key)
            return response["ContentLength"]
        except ClientError as e:
            error_msg = f"Failed to get S3 file size: {e}"
            logger.error(error_msg)
            raise S3ManagerError(error_msg) from e

    def upload_directory(
        self,
        local_dir: str,
        s3_prefix: str,
        bucket_name: Optional[str] = None,
        pattern: Optional[str] = None,
    ) -> List[str]:
        """
        Upload all files in a directory to S3.

        Args:
            local_dir: Local directory path
            s3_prefix: S3 key prefix (directory path in bucket)
            bucket_name: Optional bucket name override
            pattern: Optional file pattern to match (e.g., "*.vcf")

        Returns:
            List of S3 URIs for uploaded files
        """
        local_path = Path(local_dir)
        if not local_path.is_dir():
            raise S3ManagerError(f"Not a directory: {local_dir}")

        uploaded_files = []

        # Find all files
        if pattern:
            files = list(local_path.glob(pattern))
        else:
            files = list(local_path.rglob("*"))
            files = [f for f in files if f.is_file()]

        logger.info(f"Uploading {len(files)} files from {local_dir}")

        for file_path in files:
            # Calculate relative path for S3 key
            relative_path = file_path.relative_to(local_path)
            s3_key = f"{s3_prefix}/{relative_path}".replace("\\", "/")

            try:
                s3_uri = self.upload_file(
                    str(file_path), s3_key, bucket_name, show_progress=False
                )
                uploaded_files.append(s3_uri)
            except Exception as e:
                logger.warning(f"Failed to upload {file_path}: {e}")

        logger.info(f"Successfully uploaded {len(uploaded_files)} files")
        return uploaded_files

    def download_directory(
        self,
        s3_prefix: str,
        local_dir: str,
        bucket_name: Optional[str] = None,
        pattern: Optional[str] = None,
    ) -> List[str]:
        """
        Download all files with prefix from S3 to local directory.

        Args:
            s3_prefix: S3 key prefix
            local_dir: Local directory to save files
            bucket_name: Optional bucket name override
            pattern: Optional file pattern to match

        Returns:
            List of local file paths
        """
        local_path = Path(local_dir)
        local_path.mkdir(parents=True, exist_ok=True)

        # List all files with prefix
        s3_keys = self.list_files(s3_prefix, bucket_name)

        # Filter by pattern if provided
        if pattern:
            import fnmatch
            s3_keys = [k for k in s3_keys if fnmatch.fnmatch(k, pattern)]

        downloaded_files = []

        logger.info(f"Downloading {len(s3_keys)} files from S3")

        for s3_key in s3_keys:
            # Calculate local path
            relative_key = s3_key[len(s3_prefix) :].lstrip("/")
            local_file = local_path / relative_key

            try:
                local_file_path = self.download_file(
                    s3_key, str(local_file), bucket_name, show_progress=False
                )
                downloaded_files.append(local_file_path)
            except Exception as e:
                logger.warning(f"Failed to download {s3_key}: {e}")

        logger.info(f"Successfully downloaded {len(downloaded_files)} files")
        return downloaded_files


# Global instance
_s3_manager: Optional[S3Manager] = None


def get_s3_manager() -> S3Manager:
    """
    Get global S3 manager instance.

    Returns:
        S3Manager instance
    """
    global _s3_manager
    if _s3_manager is None:
        _s3_manager = S3Manager()
    return _s3_manager

