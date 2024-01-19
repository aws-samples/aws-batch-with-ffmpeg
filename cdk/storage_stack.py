# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0

import logging
import os

import aws_cdk as cdk
from aws_cdk import Stack
from aws_cdk import aws_ec2 as ec2
from aws_cdk import aws_ecr as ecr
from aws_cdk import aws_fsx as fsx
from aws_cdk import aws_s3 as s3
from aws_cdk import aws_ssm as ssm
from constructs import Construct

from cdk.constructs.ssm_document_lustre_preload import SSMDocumentLustrePreload

LOGLEVEL = os.environ.get("LOGLEVEL", "INFO").upper()
logging.basicConfig(level=LOGLEVEL)
logger = logging.getLogger()
logger.setLevel(LOGLEVEL)


class StorageStack(Stack):
    """Storage layer of the solution."""

    ecr_registry = None
    s3_bucket = None
    lustre_fs = None
    ssm_document: ssm.CfnDocument = None

    def __init__(self, scope: Construct, construct_id: str, vpc, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        s3_bucket = s3.Bucket(
            self,
            id="bucket",
            enforce_ssl=True,
            versioned=True,
            block_public_access=s3.BlockPublicAccess.BLOCK_ALL,
            encryption=s3.BucketEncryption.S3_MANAGED,
        )
        self.s3_bucket = s3_bucket

        # Containers registry
        ecr_registry = ecr.Repository(
            self,
            "ecr",
            repository_name="batch-ffmpeg",
            image_scan_on_push=True,
            encryption=ecr.RepositoryEncryption.AES_256,
        )
        self.ecr_registry = ecr_registry

        # Lustre FS
        lustre_enable = self.node.try_get_context(
            "batch-ffmpeg:lustre-fs:enable"
        )  # feature toggle in cdk.json
        if lustre_enable:
            lustre_subnet = vpc.select_subnets(
                subnet_type=ec2.SubnetType.PRIVATE_ISOLATED
            ).subnets[0]
            lustre_sg = ec2.SecurityGroup(
                self,
                "lustre-sg",
                vpc=vpc,
                allow_all_outbound=True,
            )
            lustre_sg.add_ingress_rule(
                peer=ec2.Peer.ipv4(vpc.vpc_cidr_block),
                connection=ec2.Port.tcp(988),
                description="FSx Lustre client port",
            )
            lustre_configuration = {
                "deployment_type": fsx.LustreDeploymentType.SCRATCH_2,
                "export_path": self.s3_bucket.s3_url_for_object(),
                "import_path": self.s3_bucket.s3_url_for_object(),
                "auto_import_policy": fsx.LustreAutoImportPolicy.NEW_CHANGED_DELETED,
            }
            self.lustre_fs = fsx.LustreFileSystem(
                self,
                "lustre-fs",
                vpc=vpc,
                vpc_subnet=lustre_subnet,
                security_group=lustre_sg,
                storage_capacity_gib=self.node.try_get_context(
                    "batch-ffmpeg:lustre-fs:storage_capacity_gi_b"
                ),
                lustre_configuration=lustre_configuration,
            )
            # SSM Document to preload Lustre FS file
            ssm_document_preload = SSMDocumentLustrePreload(
                self,
                "ssm-lustre-preload",
                lustre_fs=self.lustre_fs,
                subnet=lustre_subnet,
            )
            self.ssm_document = ssm_document_preload.ssm_document

            cdk.CfnOutput(
                self,
                "lustre-fs-dns",
                value=self.lustre_fs.dns_name,
                description="AWS Batch with FFmpeg : AWS FSx for Lustre cluster DNS name",
            )
            cdk.CfnOutput(
                self,
                "lustre-fs-mount-name",
                value=self.lustre_fs.mount_name,
                description="AWS Batch with FFmpeg : AWS FSx for Lustre mount name",
            )
        # Cloudformation outputs
        cdk.CfnOutput(
            self,
            "S3bucket",
            value=s3_bucket.bucket_name,
            description="AWS Batch with FFmpeg : S3 bucket",
        )
        cdk.CfnOutput(
            self,
            "EcrRegistry",
            value=ecr_registry.repository_name,
            description="AWS Batch with FFmpeg : Container registry",
        )
