import aws_cdk as cdk
import logging
import os
from aws_cdk import Stack, RemovalPolicy
from aws_cdk import aws_s3 as s3
from aws_cdk import aws_ec2 as ec2
from aws_cdk import aws_ecr as ecr
from aws_cdk import aws_fsx as fsx
from aws_cdk import aws_ssm as ssm
from constructs import Construct
from typing import Optional

from infrastructure.constructs.ssm_document_lustre_preload import (
    SSMDocumentLustrePreload,
)

LOGLEVEL = os.environ.get("LOGLEVEL", "INFO").upper()
logging.basicConfig(level=LOGLEVEL)
logger = logging.getLogger()
logger.setLevel(LOGLEVEL)


class StorageStack(Stack):
    def __init__(
        self, scope: Construct, construct_id: str, vpc: ec2.IVpc, **kwargs
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)

        self.vpc = vpc
        self.s3_bucket = self.create_s3_bucket()
        self.ecr_repository = self.create_ecr_repository()
        self.lustre_fs, self.ssm_document = self.create_lustre_filesystem()
        self.add_outputs()

    def create_s3_bucket(self) -> s3.Bucket:
        return s3.Bucket(
            self,
            "Bucket",
            encryption=s3.BucketEncryption.S3_MANAGED,
            enforce_ssl=True,
            versioned=True,
            block_public_access=s3.BlockPublicAccess.BLOCK_ALL,
            removal_policy=RemovalPolicy.RETAIN,
        )

    def create_ecr_repository(self) -> ecr.Repository:
        return ecr.Repository(
            self,
            "Registry",
            repository_name="batch-ffmpeg",
            image_scan_on_push=True,
            encryption=ecr.RepositoryEncryption.AES_256,
            removal_policy=RemovalPolicy.DESTROY,
            empty_on_delete=True,
        )

    def create_lustre_filesystem(
        self,
    ) -> tuple[Optional[fsx.LustreFileSystem], Optional[ssm.CfnDocument]]:
        """Create an FSx for Lustre file system and associated SSM document if
        enabled.

        Returns:
            tuple[Optional[fsx.LustreFileSystem], Optional[ssm.CfnDocument]]:
                The created Lustre file system and SSM document, or (None, None) if not enabled.
        """
        lustre_enable = self.node.try_get_context("batch-ffmpeg:lustre-fs:enable")
        if str(lustre_enable).lower() == "false":
            return None, None
        logging.info("Creating FSx for Lustre file system")
        lustre_subnet = self.vpc.select_subnets(
            subnet_type=ec2.SubnetType.PRIVATE_ISOLATED
        ).subnets[0]

        lustre_sg = ec2.SecurityGroup(
            self,
            "LustreSecurityGroup",
            vpc=self.vpc,
            description="Security group for FSx Lustre",
            allow_all_outbound=True,
        )
        lustre_sg.add_ingress_rule(
            peer=ec2.Peer.ipv4(self.vpc.vpc_cidr_block),
            connection=ec2.Port.tcp(988),
            description="FSx Lustre client port",
        )

        lustre_fs = fsx.LustreFileSystem(
            self,
            "LustreFileSystem",
            vpc=self.vpc,
            vpc_subnet=lustre_subnet,
            security_group=lustre_sg,
            storage_capacity_gib=self.node.try_get_context(
                "batch-ffmpeg:lustre-fs:storage_capacity_gi_b"
            ),
            lustre_configuration=fsx.LustreConfiguration(
                deployment_type=fsx.LustreDeploymentType.SCRATCH_2,
                export_path=self.s3_bucket.s3_url_for_object(),
                import_path=self.s3_bucket.s3_url_for_object(),
                auto_import_policy=fsx.LustreAutoImportPolicy.NEW_CHANGED_DELETED,
            ),
        )

        ssm_document = self.create_ssm_document(lustre_fs, lustre_subnet)

        return lustre_fs, ssm_document

    def create_ssm_document(
        self, lustre_fs: fsx.LustreFileSystem, subnet: ec2.ISubnet
    ) -> ssm.CfnDocument:
        """Create an SSM document for preloading data into the Lustre file
        system.

        Args:
            lustre_fs (fsx.LustreFileSystem): The Lustre file system to preload data into.
            subnet (ec2.ISubnet): The subnet to use for the preload process.

        Returns:
            ssm.CfnDocument: The created SSM document.
        """

        ssm_document_preload = SSMDocumentLustrePreload(
            self,
            "SSMLustrePreload",
            lustre_fs=lustre_fs,
            subnet=subnet,
        )
        return ssm_document_preload.ssm_document

    def add_outputs(self) -> None:
        """Add CloudFormation outputs for the created resources."""
        cdk.CfnOutput(
            self,
            "DataBucketName",
            value=self.s3_bucket.bucket_name,
            description="Name of the S3 bucket for data storage",
            key="DataBucketName",
        )

        cdk.CfnOutput(
            self,
            "ECRRepositoryName",
            value=self.ecr_repository.repository_name,
            description="Name of the ECR repository for FFmpeg container images",
            key="ECRRepositoryName",
        )

        if self.lustre_fs:
            cdk.CfnOutput(
                self,
                "LustreFSDNSName",
                value=self.lustre_fs.dns_name,
                description="DNS name of the FSx for Lustre file system",
                key="LustreFSDNSName",
            )

            cdk.CfnOutput(
                self,
                "LustreFSMountName",
                value=self.lustre_fs.mount_name,
                description="Mount name of the FSx for Lustre file system",
                key="LustreFSMountName",
            )
