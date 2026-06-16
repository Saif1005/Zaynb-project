"""AWS Batch manager module for submitting and managing genomic processing jobs."""

from typing import Optional, Dict, List
from botocore.exceptions import ClientError
import boto3
from loguru import logger

from config.aws_config import aws_config


class BatchManagerError(Exception):
    """Custom exception for AWS Batch operations."""

    pass


class BatchManager:
    """Manager for AWS Batch job submission and monitoring."""

    def __init__(
        self,
        job_queue: Optional[str] = None,
        job_definition: Optional[str] = None,
        region: Optional[str] = None,
    ):
        """
        Initialize AWS Batch manager.

        Args:
            job_queue: Optional job queue name
            job_definition: Optional job definition name
            region: Optional AWS region (defaults to config)
        """
        self.region = region or aws_config.region
        self.job_queue = job_queue
        self.job_definition = job_definition

        try:
            self.batch_client = boto3.client("batch", region_name=self.region)
            logger.info(f"AWS Batch client initialized for region: {self.region}")
        except Exception as e:
            logger.error(f"Failed to initialize Batch client: {e}")
            raise BatchManagerError(f"Batch initialization failed: {e}") from e

    def submit_job(
        self,
        job_name: str,
        command: List[str],
        job_queue: Optional[str] = None,
        job_definition: Optional[str] = None,
        environment: Optional[Dict[str, str]] = None,
        vcpus: Optional[int] = None,
        memory: Optional[int] = None,
        depends_on: Optional[List[Dict]] = None,
        timeout: Optional[int] = None,
    ) -> str:
        """
        Submit a job to AWS Batch.

        Args:
            job_name: Unique job name
            command: Command to execute (list of strings)
            job_queue: Optional job queue override
            job_definition: Optional job definition override
            environment: Optional environment variables
            vcpus: Optional vCPU override
            memory: Optional memory override (MB)
            depends_on: Optional list of job dependencies
            timeout: Optional timeout in seconds

        Returns:
            Job ID

        Raises:
            BatchManagerError: If submission fails
        """
        job_queue = job_queue or self.job_queue
        job_definition = job_definition or self.job_definition

        if not job_queue:
            raise BatchManagerError("Job queue is required")
        if not job_definition:
            raise BatchManagerError("Job definition is required")

        job_config = {
            "jobName": job_name,
            "jobQueue": job_queue,
            "jobDefinition": job_definition,
            "containerOverrides": {
                "command": command,
            },
        }

        # Add environment variables
        if environment:
            env_list = [
                {"name": k, "value": v} for k, v in environment.items()
            ]
            job_config["containerOverrides"]["environment"] = env_list

        # Add resource overrides
        resource_requirements = []
        if vcpus:
            resource_requirements.append({"type": "VCPU", "value": str(vcpus)})
        if memory:
            resource_requirements.append({"type": "MEMORY", "value": str(memory)})
        if resource_requirements:
            job_config["containerOverrides"]["resourceRequirements"] = resource_requirements

        # Add dependencies
        if depends_on:
            job_config["dependsOn"] = depends_on

        # Add timeout
        if timeout:
            job_config["timeout"] = {"attemptDurationSeconds": timeout}

        try:
            logger.info(f"Submitting Batch job: {job_name}")
            response = self.batch_client.submit_job(**job_config)
            job_id = response["jobId"]
            logger.info(f"Job submitted successfully: {job_id}")
            return job_id

        except ClientError as e:
            error_msg = f"Failed to submit Batch job: {e}"
            logger.error(error_msg)
            raise BatchManagerError(error_msg) from e

    def get_job_status(self, job_id: str) -> Dict:
        """
        Get status of a Batch job.

        Args:
            job_id: Job ID

        Returns:
            Dictionary with job status information

        Raises:
            BatchManagerError: If operation fails
        """
        try:
            response = self.batch_client.describe_jobs(jobs=[job_id])
            if not response["jobs"]:
                raise BatchManagerError(f"Job not found: {job_id}")

            job = response["jobs"][0]
            return {
                "job_id": job_id,
                "job_name": job["jobName"],
                "status": job["status"],
                "status_reason": job.get("statusReason"),
                "created_at": job.get("createdAt"),
                "started_at": job.get("startedAt"),
                "stopped_at": job.get("stoppedAt"),
                "exit_code": job.get("container", {}).get("exitCode"),
            }

        except ClientError as e:
            error_msg = f"Failed to get job status: {e}"
            logger.error(error_msg)
            raise BatchManagerError(error_msg) from e

    def wait_for_job(
        self, job_id: str, timeout: int = 7200, poll_interval: int = 30
    ) -> Dict:
        """
        Wait for job to complete.

        Args:
            job_id: Job ID
            timeout: Maximum wait time in seconds
            poll_interval: Polling interval in seconds

        Returns:
            Final job status

        Raises:
            BatchManagerError: If timeout or error occurs
        """
        import time

        logger.info(f"Waiting for job {job_id} to complete (timeout: {timeout}s)")

        start_time = time.time()
        while True:
            status = self.get_job_status(job_id)
            current_status = status["status"]

            if current_status in ("SUCCEEDED", "FAILED"):
                logger.info(f"Job {job_id} completed with status: {current_status}")
                return status

            if time.time() - start_time > timeout:
                raise BatchManagerError(
                    f"Timeout waiting for job {job_id} to complete"
                )

            time.sleep(poll_interval)

    def cancel_job(self, job_id: str, reason: Optional[str] = None) -> None:
        """
        Cancel a running job.

        Args:
            job_id: Job ID
            reason: Optional cancellation reason

        Raises:
            BatchManagerError: If operation fails
        """
        try:
            logger.info(f"Cancelling job: {job_id}")
            self.batch_client.cancel_job(
                jobId=job_id, reason=reason or "User requested cancellation"
            )
            logger.info(f"Cancel command sent for job: {job_id}")
        except ClientError as e:
            error_msg = f"Failed to cancel job: {e}"
            logger.error(error_msg)
            raise BatchManagerError(error_msg) from e

    def list_jobs(
        self,
        job_queue: Optional[str] = None,
        job_status: Optional[str] = None,
        max_results: int = 100,
    ) -> List[Dict]:
        """
        List jobs in a queue.

        Args:
            job_queue: Optional job queue name
            job_status: Optional status filter (SUBMITTED, PENDING, RUNNABLE, RUNNING, SUCCEEDED, FAILED)
            max_results: Maximum number of results

        Returns:
            List of job information dictionaries
        """
        job_queue = job_queue or self.job_queue
        if not job_queue:
            raise BatchManagerError("Job queue is required")

        try:
            list_config = {
                "jobQueue": job_queue,
                "maxResults": max_results,
            }
            if job_status:
                list_config["filters"] = [{"name": "JOB_STATUS", "values": [job_status]}]

            response = self.batch_client.list_jobs(**list_config)
            jobs = []

            for job_summary in response.get("jobSummaryList", []):
                jobs.append({
                    "job_id": job_summary["jobId"],
                    "job_name": job_summary["jobName"],
                    "status": job_summary["status"],
                    "created_at": job_summary.get("createdAt"),
                    "started_at": job_summary.get("startedAt"),
                })

            logger.debug(f"Found {len(jobs)} jobs")
            return jobs

        except ClientError as e:
            logger.error(f"Failed to list jobs: {e}")
            return []

    def create_job_definition(
        self,
        job_definition_name: str,
        image_uri: str,
        vcpus: int = 4,
        memory: int = 8192,
        job_role_arn: Optional[str] = None,
        execution_role_arn: Optional[str] = None,
    ) -> str:
        """
        Create or update a job definition.

        Args:
            job_definition_name: Job definition name
            image_uri: Docker image URI
            vcpus: Number of vCPUs
            memory: Memory in MB
            job_role_arn: Optional IAM role ARN for job
            execution_role_arn: Optional IAM role ARN for execution

        Returns:
            Job definition ARN

        Raises:
            BatchManagerError: If creation fails
        """
        container_properties = {
            "image": image_uri,
            "vcpus": vcpus,
            "memory": memory,
            "privileged": True,  # Required for GPU access
        }

        if job_role_arn:
            container_properties["jobRoleArn"] = job_role_arn
        if execution_role_arn:
            container_properties["executionRoleArn"] = execution_role_arn

        try:
            logger.info(f"Creating job definition: {job_definition_name}")
            response = self.batch_client.register_job_definition(
                jobDefinitionName=job_definition_name,
                type="container",
                containerProperties=container_properties,
            )
            job_def_arn = response["jobDefinitionArn"]
            logger.info(f"Job definition created: {job_def_arn}")
            return job_def_arn

        except ClientError as e:
            error_msg = f"Failed to create job definition: {e}"
            logger.error(error_msg)
            raise BatchManagerError(error_msg) from e


# Global instance
_batch_manager: Optional[BatchManager] = None


def get_batch_manager() -> BatchManager:
    """
    Get global Batch manager instance.

    Returns:
        BatchManager instance
    """
    global _batch_manager
    if _batch_manager is None:
        _batch_manager = BatchManager()
    return _batch_manager

