"""EC2 manager module for managing GPU instances for Parabricks processing."""

import time
from typing import Optional, Dict, List
from botocore.exceptions import ClientError
import boto3
from loguru import logger

from config.aws_config import aws_config


class EC2ManagerError(Exception):
    """Custom exception for EC2 operations."""

    pass


class EC2Manager:
    """Manager for EC2 GPU instances (launch, stop, monitor)."""

    def __init__(self, region: Optional[str] = None):
        """
        Initialize EC2 manager.

        Args:
            region: Optional AWS region (defaults to config)
        """
        self.region = region or aws_config.region

        try:
            self.ec2_client = boto3.client("ec2", region_name=self.region)
            self.ec2_resource = boto3.resource("ec2", region_name=self.region)
            logger.info(f"EC2 client initialized for region: {self.region}")
        except Exception as e:
            logger.error(f"Failed to initialize EC2 client: {e}")
            raise EC2ManagerError(f"EC2 initialization failed: {e}") from e

    def launch_instance(
        self,
        instance_type: Optional[str] = None,
        ami_id: Optional[str] = None,
        key_name: Optional[str] = None,
        security_group_ids: Optional[List[str]] = None,
        subnet_id: Optional[str] = None,
        user_data: Optional[str] = None,
        spot: bool = False,
        spot_price: Optional[str] = None,
        tags: Optional[Dict[str, str]] = None,
        availability_zone: Optional[str] = None,
    ) -> str:
        """
        Launch an EC2 instance.

        Args:
            instance_type: Instance type (defaults to p3.2xlarge)
            ami_id: AMI ID (defaults to config)
            key_name: SSH key pair name
            security_group_ids: List of security group IDs
            subnet_id: Subnet ID for VPC
            user_data: User data script (for setup)
            spot: Use spot instance (default: False)
            spot_price: Maximum spot price
            tags: Dictionary of tags to apply

        Returns:
            Instance ID

        Raises:
            EC2ManagerError: If launch fails
        """
        instance_type = instance_type or aws_config.ec2_instance_type
        ami_id = ami_id or aws_config.ec2_ami_id

        if not ami_id:
            raise EC2ManagerError("AMI ID is required to launch instance")

        launch_config = {
            "ImageId": ami_id,
            "InstanceType": instance_type,
            "MinCount": 1,
            "MaxCount": 1,
        }

        # Add key pair if provided
        if key_name:
            launch_config["KeyName"] = key_name

        # Add security groups
        if security_group_ids:
            launch_config["SecurityGroupIds"] = security_group_ids

        # Add subnet for VPC
        if subnet_id:
            launch_config["SubnetId"] = subnet_id

        # Add user data (base64 encoded automatically by boto3)
        if user_data:
            launch_config["UserData"] = user_data

        # Add IAM instance profile if configured
        iam_role = aws_config.ec2_iam_role if hasattr(aws_config, "ec2_iam_role") else None
        if iam_role:
            launch_config["IamInstanceProfile"] = {"Name": iam_role}

        # Configure spot instance if requested
        if spot:
            spot_config = {
                "MarketType": "spot",
                "SpotOptions": {
                    "SpotInstanceType": "one-time",
                },
            }
            if spot_price:
                spot_config["SpotOptions"]["MaxPrice"] = spot_price
            launch_config["InstanceMarketOptions"] = spot_config

        try:
            logger.info(
                f"Launching EC2 instance: {instance_type} "
                f"(AMI: {ami_id}, Spot: {spot})"
            )

            response = self.ec2_client.run_instances(**launch_config)
            instance_id = response["Instances"][0]["InstanceId"]

            # Add tags
            if tags:
                tags_list = [
                    {"Key": k, "Value": v} for k, v in tags.items()
                ]
                tags_list.append({"Key": "Name", "Value": tags.get("Name", "genomic-pipeline")})
                self.ec2_client.create_tags(
                    Resources=[instance_id], Tags=tags_list
                )

            logger.info(f"Instance launched: {instance_id}")
            return instance_id

        except ClientError as e:
            error_msg = f"Failed to launch EC2 instance: {e}"
            logger.error(error_msg)
            raise EC2ManagerError(error_msg) from e

    def wait_for_instance(
        self, instance_id: str, state: str = "running", timeout: int = 600
    ) -> Dict:
        """
        Wait for instance to reach a specific state.

        Args:
            instance_id: Instance ID
            state: Target state (running, stopped, etc.)
            timeout: Maximum wait time in seconds

        Returns:
            Instance state information

        Raises:
            EC2ManagerError: If timeout or error occurs
        """
        logger.info(f"Waiting for instance {instance_id} to reach state: {state}")

        start_time = time.time()
        while True:
            try:
                response = self.ec2_client.describe_instances(
                    InstanceIds=[instance_id]
                )
                instance = response["Reservations"][0]["Instances"][0]
                current_state = instance["State"]["Name"]

                if current_state == state:
                    logger.info(
                        f"Instance {instance_id} reached state: {state}"
                    )
                    return instance

                if time.time() - start_time > timeout:
                    raise EC2ManagerError(
                        f"Timeout waiting for instance {instance_id} "
                        f"to reach state {state}"
                    )

                time.sleep(10)

            except ClientError as e:
                error_msg = f"Error checking instance state: {e}"
                logger.error(error_msg)
                raise EC2ManagerError(error_msg) from e

    def get_instance_info(self, instance_id: str) -> Dict:
        """
        Get information about an instance.

        Args:
            instance_id: Instance ID

        Returns:
            Dictionary with instance information

        Raises:
            EC2ManagerError: If operation fails
        """
        try:
            response = self.ec2_client.describe_instances(
                InstanceIds=[instance_id]
            )
            if not response["Reservations"]:
                raise EC2ManagerError(f"Instance not found: {instance_id}")

            instance = response["Reservations"][0]["Instances"][0]
            return {
                "instance_id": instance_id,
                "state": instance["State"]["Name"],
                "instance_type": instance["InstanceType"],
                "public_ip": instance.get("PublicIpAddress"),
                "private_ip": instance.get("PrivateIpAddress"),
                "launch_time": instance["LaunchTime"],
                "tags": {tag["Key"]: tag["Value"] for tag in instance.get("Tags", [])},
            }

        except ClientError as e:
            error_msg = f"Failed to get instance info: {e}"
            logger.error(error_msg)
            raise EC2ManagerError(error_msg) from e

    def stop_instance(self, instance_id: str, force: bool = False) -> None:
        """
        Stop an EC2 instance.

        Args:
            instance_id: Instance ID
            force: Force stop (default: False)

        Raises:
            EC2ManagerError: If operation fails
        """
        try:
            logger.info(f"Stopping instance: {instance_id}")
            self.ec2_client.stop_instances(
                InstanceIds=[instance_id], Force=force
            )
            logger.info(f"Stop command sent for instance: {instance_id}")
        except ClientError as e:
            error_msg = f"Failed to stop instance: {e}"
            logger.error(error_msg)
            raise EC2ManagerError(error_msg) from e

    def terminate_instance(self, instance_id: str) -> None:
        """
        Terminate an EC2 instance.

        Args:
            instance_id: Instance ID

        Raises:
            EC2ManagerError: If operation fails
        """
        try:
            logger.info(f"Terminating instance: {instance_id}")
            self.ec2_client.terminate_instances(InstanceIds=[instance_id])
            logger.info(f"Terminate command sent for instance: {instance_id}")
        except ClientError as e:
            error_msg = f"Failed to terminate instance: {e}"
            logger.error(error_msg)
            raise EC2ManagerError(error_msg) from e

    def list_instances(
        self,
        filters: Optional[Dict] = None,
        state: Optional[str] = None,
    ) -> List[Dict]:
        """
        List EC2 instances matching filters.

        Args:
            filters: Optional EC2 filters
            state: Optional state filter (running, stopped, etc.)

        Returns:
            List of instance information dictionaries
        """
        try:
            ec2_filters = []
            if filters:
                ec2_filters.extend(
                    [{"Name": k, "Values": [v]} for k, v in filters.items()]
                )
            if state:
                ec2_filters.append({"Name": "instance-state-name", "Values": [state]})

            response = self.ec2_client.describe_instances(Filters=ec2_filters)

            instances = []
            for reservation in response["Reservations"]:
                for instance in reservation["Instances"]:
                    instances.append({
                        "instance_id": instance["InstanceId"],
                        "state": instance["State"]["Name"],
                        "instance_type": instance["InstanceType"],
                        "public_ip": instance.get("PublicIpAddress"),
                        "private_ip": instance.get("PrivateIpAddress"),
                        "launch_time": instance["LaunchTime"],
                    })

            logger.debug(f"Found {len(instances)} instances")
            return instances

        except ClientError as e:
            logger.error(f"Failed to list instances: {e}")
            return []

    def get_instance_public_ip(self, instance_id: str) -> Optional[str]:
        """
        Get public IP address of an instance.

        Args:
            instance_id: Instance ID

        Returns:
            Public IP address or None
        """
        info = self.get_instance_info(instance_id)
        return info.get("public_ip")

    def create_security_group(
        self,
        name: str,
        description: str,
        vpc_id: Optional[str] = None,
        ingress_rules: Optional[List[Dict]] = None,
    ) -> str:
        """
        Create a security group for EC2 instances.

        Args:
            name: Security group name
            description: Security group description
            vpc_id: Optional VPC ID
            ingress_rules: List of ingress rules

        Returns:
            Security group ID

        Raises:
            EC2ManagerError: If creation fails
        """
        try:
            # Create security group
            sg_config = {
                "GroupName": name,
                "Description": description,
            }
            if vpc_id:
                sg_config["VpcId"] = vpc_id

            response = self.ec2_client.create_security_group(**sg_config)
            sg_id = response["GroupId"]

            logger.info(f"Created security group: {sg_id} ({name})")

            # Add ingress rules
            if ingress_rules:
                self.ec2_client.authorize_security_group_ingress(
                    GroupId=sg_id, IpPermissions=ingress_rules
                )
                logger.info(f"Added {len(ingress_rules)} ingress rules")

            return sg_id

        except ClientError as e:
            error_msg = f"Failed to create security group: {e}"
            logger.error(error_msg)
            raise EC2ManagerError(error_msg) from e


# Global instance
_ec2_manager: Optional[EC2Manager] = None


def get_ec2_manager() -> EC2Manager:
    """
    Get global EC2 manager instance.

    Returns:
        EC2Manager instance
    """
    global _ec2_manager
    if _ec2_manager is None:
        _ec2_manager = EC2Manager()
    return _ec2_manager

