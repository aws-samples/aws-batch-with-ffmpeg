# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0
import os

import aws_cdk as cdk

from constructs import Construct

from aws_cdk import (
    Stack,
    aws_ecr as ecr,
    aws_logs as logs,
    aws_iam as iam,
)

from cdk.constructs.video_batch_job import VideoBatchJob


class RegistryStack(Stack):
    """Container registry of the solution"""
    
    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        
        super().__init__(scope, construct_id, **kwargs)
        
        # Containers definition
        ecr_registry = ecr.Repository(self, "ecr", repository_name="batch-ffmpeg", image_scan_on_push=True)
        self.ecr_registry = ecr_registry
        
        cdk.CfnOutput(self, "EcrRegistry", value=ecr_registry.repository_name,
                      description="AWS Batch nodes can access to this S3 bucket.")
