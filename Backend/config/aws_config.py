"""AWS configuration module."""

import os
from typing import Optional, List, Dict
from dataclasses import dataclass, field
from dotenv import load_dotenv

load_dotenv()
load_dotenv(".env.cloud")


@dataclass
class AWSConfig:
    """Configuration for AWS services (S3, EC2, Batch, CloudWatch)."""

    region: str
    availability_zone: Optional[str] = None
    account_id: str = ""
    s3_bucket_name: str = "genomic-cancer-pipeline"
    s3_input_bucket: str = "genomic-cancer-pipeline-input"
    s3_output_bucket: str = "genomic-cancer-pipeline-output"
    s3_reference_bucket: str = "genomic-references"
    ec2_instance_type: str = "t3.xlarge"  # ✅ Changé pour t3.xlarge
    ec2_ami_id: Optional[str] = None
    ec2_availability_zones: Optional[List[str]] = None
    cloudwatch_log_group: str = "genomic-cancer-pipeline"
    
    # ✅ Mapping des AMIs Ubuntu 22.04 par région
    UBUNTU_22_04_AMIS: Dict[str, str] = field(default_factory=lambda: {
        'us-east-1': 'ami-0030e4319cbf4dbf2',
        'us-east-2': 'ami-0c7217cdde317cfec',
        'us-west-1': 'ami-0cbd40f694b804622',
        'us-west-2': 'ami-055c254ebd87b4dba',  # ✅ Ton AMI actuel
        'eu-west-1': 'ami-0905a3c97561e0b69',
        'eu-central-1': 'ami-0a485299eeb98b979',
        'ap-southeast-1': 'ami-0df7a207adb9748c7',
    })
    
    # Mapping des Security Groups par région (utiliser SECURITY_GROUP_ID depuis .env en priorité)
    SECURITY_GROUPS: Dict[str, str] = field(default_factory=lambda: {
        'us-east-1': 'sg-0f37e96ffff9392c5',
        'us-west-2': 'sg-0f37e96ffff9392c5',  # Security group réel depuis .env
    })
    
    # ✅ Mapping des zones de disponibilité par région
    AVAILABILITY_ZONES: Dict[str, List[str]] = field(default_factory=lambda: {
        'us-east-1': [None, 'us-east-1a', 'us-east-1d', 'us-east-1f'],
        'us-west-2': [None, 'us-west-2a', 'us-west-2b', 'us-west-2c'],  # ✅ us-west-2
        'eu-west-1': [None, 'eu-west-1a', 'eu-west-1b', 'eu-west-1c'],
    })

    def __post_init__(self):
        """Initialize availability zones and AMI based on region."""
        # Set availability zones for the region
        if self.ec2_availability_zones is None:
            self.ec2_availability_zones = self.AVAILABILITY_ZONES.get(
                self.region, 
                [None]  # Default: let AWS choose
            )
        
        # Set AMI if not provided
        if self.ec2_ami_id is None:
            self.ec2_ami_id = self.UBUNTU_22_04_AMIS.get(
                self.region,
                self.UBUNTU_22_04_AMIS['us-east-1']  # Fallback
            )

    @classmethod
    def from_env(cls) -> "AWSConfig":
        """Create AWSConfig from environment variables."""
        return cls(
            region=os.getenv("AWS_REGION", "us-west-2"),
            availability_zone=os.getenv("AWS_AVAILABILITY_ZONE"),
            account_id=os.getenv("AWS_ACCOUNT_ID", "622994489865"),
            # Utiliser les noms de buckets réels depuis .env (avec suffixes Terraform)
            s3_bucket_name=os.getenv("S3_BUCKET_NAME", "genomic-cancer-pipeline"),
            s3_input_bucket=os.getenv("S3_INPUT_BUCKET", "genomic-cancer-pipeline-input-dev-622994489865"),
            s3_output_bucket=os.getenv("S3_OUTPUT_BUCKET", "genomic-cancer-pipeline-output-dev-622994489865"),
            s3_reference_bucket=os.getenv("S3_REFERENCE_BUCKET", "genomic-references-dev-622994489865"),
            ec2_instance_type=os.getenv("EC2_INSTANCE_TYPE", "t3.xlarge"),
            ec2_ami_id=os.getenv("EC2_AMI_ID"),
            cloudwatch_log_group=os.getenv("CLOUDWATCH_LOG_GROUP", "genomic-cancer-pipeline-dev"),
        )

    @property
    def security_group_id(self) -> Optional[str]:
        """Get security group ID for the current region."""
        # Priorité: SECURITY_GROUP_ID depuis .env, puis mapping par région
        return os.getenv(
            "SECURITY_GROUP_ID",
            self.SECURITY_GROUPS.get(self.region)
        )
    
    @property
    def key_name(self) -> str:
        """Get SSH key name."""
        return os.getenv("KEY_NAME", "genomic-pipeline-key")

    @property
    def reference_genome_s3(self) -> str:
        """Get S3 path to reference genome."""
        return os.getenv(
            "REFERENCE_GENOME_S3",
            f"s3://{self.s3_reference_bucket}/hg38/hg38.fa",
        )

    @property
    def known_sites_vcf_s3(self) -> str:
        """Get S3 path to known sites VCF."""
        return os.getenv(
            "KNOWN_SITES_VCF_S3",
            f"s3://{self.s3_reference_bucket}/hg38/known_sites.vcf",
        )
    
    def get_instance_info(self) -> Dict[str, str]:
        """Get current instance configuration info."""
        return {
            "region": self.region,
            "instance_type": self.ec2_instance_type,
            "ami_id": self.ec2_ami_id,
            "security_group": self.security_group_id,
            "key_name": self.key_name,
            "availability_zones": self.ec2_availability_zones,
        }


# Global instance
aws_config = AWSConfig.from_env()