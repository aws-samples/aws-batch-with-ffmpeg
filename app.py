#!/usr/bin/env python3
# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0
import os
import aws_cdk as cdk
from aws_cdk import Aspects
import cdk_nag

from cdk.batch_job_ffmpeg_stack import BatchJobFfmpegStack
from cdk.registry_stack import RegistryStack
from cdk.metrics_stack import MetricsStack
from cdk.api_stack import ApiStack

env = cdk.Environment(
    account=os.environ.get("CDK_DEPLOY_ACCOUNT", os.environ["CDK_DEFAULT_ACCOUNT"]),
    region=os.environ.get("CDK_DEPLOY_REGION", os.environ["CDK_DEFAULT_REGION"]),
)

app = cdk.App()
cdk.Tags.of(app).add("application", "batch-ffmpeg")

registry_stack = RegistryStack(app, "batch-ffmpeg-registry-stack", env=env)
batch_stack = BatchJobFfmpegStack(
    app, "batch-ffmpeg-stack", ecr_registry=registry_stack.ecr_registry, env=env,
    description="Main stack with AWS Batch (uksb-1tg6b0m8t)"
)
metrics_stack = MetricsStack(
    app, "batch-ffmpeg-metrics-stack", s3_bucket=batch_stack.s3_bucket, env=env
)
ApiStack(
    app,
    "batch-ffmpeg-api-stack",
    video_batch_jobs=batch_stack.video_batch_jobs,
    metrics_handler=metrics_stack.handler,
    env=env,
)

# cdk nag
cdk_nag.NagSuppressions.add_resource_suppressions(
    app,
    apply_to_children=True,
    suppressions=[
        cdk_nag.NagPackSuppression(
            id="AwsSolutions-IAM4",
            reason="AWS Managed Service Role and AWS managed XRay Policy",
            applies_to=[
                "Policy::arn:<AWS::Partition>:iam::aws:policy/service-role/AmazonAPIGatewayPushToCloudWatchLogs",
                "Policy::arn:<AWS::Partition>:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole",
                "Policy::arn:<AWS::Partition>:iam::aws:policy/service-role/AWSBatchServiceRole",
                "Policy::arn:<AWS::Partition>:iam::aws:policy/AWSXrayWriteOnlyAccess",
                "Policy::arn:<AWS::Partition>:iam::aws:policy/service-role/AmazonAPIGatewayPushToCloudWatchLogs",
                "Policy::arn:<AWS::Partition>:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy",
                "Policy::arn:aws:iam::aws:policy/service-role/AWSGlueServiceRole",
                "Policy::arn:<AWS::Partition>:iam::aws:policy/service-role/AmazonEC2ContainerServiceforEC2Role",
            ],
        ),
        cdk_nag.NagPackSuppression(
            id="AwsSolutions-IAM5",
            reason="AWS Managed Service Role and AWS managed XRay Policy",
            applies_to=[
                f"Resource::arn:aws:batch:{os.getenv('CDK_DEFAULT_REGION')}:{os.getenv('CDK_DEFAULT_ACCOUNT')}"
                f":job-queue/batch-ffmpeg-job-queue-*",
                f"Resource::arn:aws:batch:{os.getenv('CDK_DEFAULT_REGION')}:{os.getenv('CDK_DEFAULT_ACCOUNT')}"
                f":job-definition/batch-ffmpeg-job-definition-*",
                f"Resource::arn:aws:ssm:{os.getenv('CDK_DEFAULT_REGION')}:{os.getenv('CDK_DEFAULT_ACCOUNT')}"
                f":parameter/batch-ffmpeg/*",
                "Action::s3:Abort*",
                "Action::s3:DeleteObject*",
                "Action::s3:List*",
                "Action::s3:GetBucket*",
                "Action::s3:GetObject*",
                "Resource::<bucket43879C71.Arn>/*",
                "Resource::*",
            ],
        ),
        {"id": "AwsSolutions-COG4", "reason": "API Gateway secured by IAM"},
    ],
)
Aspects.of(app).add(
    cdk_nag.AwsSolutionsChecks(log_ignores=True, verbose=True, reports=True)
)

app.synth()
