# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0

import aws_cdk as cdk
from aws_cdk import Stack
from aws_cdk import aws_ecr as ecr
from constructs import Construct


class RegistryStack(Stack):
    """Container registry of the solution."""

    ecr_registry = None

    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # Containers definition
        ecr_registry = ecr.Repository(
            self,
            "ecr",
            repository_name="batch-ffmpeg",
            image_scan_on_push=True,
            encryption=ecr.RepositoryEncryption.AES_256,
        )
        self.ecr_registry = ecr_registry

        cdk.CfnOutput(
            self,
            "EcrRegistry",
            value=ecr_registry.repository_name,
            description="AWS Batch nodes can access to this S3 bucket.",
        )
