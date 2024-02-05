#!/usr/bin/env python3
# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0
import os

import aws_cdk as cdk
import aws_cdk.aws_servicecatalogappregistry_alpha as appreg
import cdk_nag
from aws_cdk import Aspects

from cdk.api_stack import ApiStack
from cdk.batch_stack import BatchStack
from cdk.landing_zone_stack import LandingZoneStack
from cdk.metrics_stack import MetricsStack
from cdk.registry_stack import RegistryStack
from cdk.sfn_stack import SfnStack
from cdk.storage_stack import StorageStack

account = os.environ.get("CDK_DEPLOY_ACCOUNT", os.environ["CDK_DEFAULT_ACCOUNT"])
region = os.environ.get("CDK_DEPLOY_REGION", os.environ["CDK_DEFAULT_REGION"])

env = cdk.Environment(
    account=account,
    region=region,
)

app = cdk.App()
cdk.Tags.of(app).add("application", "batch-ffmpeg")

registry_stack = RegistryStack(app, "batch-ffmpeg-registry-stack", env=env)

landing_zone_stack = LandingZoneStack(
    app, "batch-ffmpeg-landing-stack", env=env, description="AWS Batch with FFmpeg"
)
storage_stack = StorageStack(
    app,
    "batch-ffmpeg-storage-stack",
    env=env,
    description="AWS Batch with FFmpeg",
    vpc=landing_zone_stack.vpc,
)

batch_stack = BatchStack(
    app,
    "batch-ffmpeg-stack",
    ecr_registry=storage_stack.ecr_registry,
    env=env,
    vpc=landing_zone_stack.vpc,
    s3_bucket=storage_stack.s3_bucket,
    lustre_fs=storage_stack.lustre_fs,
    description="AWS Batch with FFmpeg: Main stack (uksb-1tg6b0m8t)",
)
metrics_stack = MetricsStack(
    app,
    "batch-ffmpeg-metrics-stack",
    s3_bucket=storage_stack.s3_bucket,
    env=env,
    description="AWS Batch with FFmpeg : Metrics stack",
)

sfn_stack = SfnStack(
    app,
    "batch-ffmpeg-sfn-stack",
    s3_bucket=storage_stack.s3_bucket,
    env=env,
    description="AWS Batch with FFmpeg : AWS Step Functions",
)

api_stack = ApiStack(
    app,
    "batch-ffmpeg-api-stack",
    video_batch_jobs=batch_stack.video_batch_jobs,
    lustre_fs=storage_stack.lustre_fs,
    sfn_state_machine=sfn_stack.sfn_state_machine,
    ssm_document=storage_stack.ssm_document,
    env=env,
    description="AWS Batch with FFmpeg : API Gateway",
)
application = appreg.ApplicationAssociator(
    app,
    "batch-ffmepg-app",
    applications=[
        appreg.TargetApplication.create_application_stack(
            application_name="batch-ffmpeg",
            description="AWS Batch with FFMPEG : Application",
            stack_name="batch-ffmpeg-application",
            env=env,
        )
    ],
)
application.node.add_dependency(landing_zone_stack)
application.node.add_dependency(storage_stack)
application.node.add_dependency(metrics_stack)
application.node.add_dependency(api_stack)
application.node.add_dependency(batch_stack)
app.synth()
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
                f"Resource::arn:aws:batch:{region}:{account}"
                ":job-queue/batch-ffmpeg-job-queue-*",
                f"Resource::arn:<AWS::Partition>:logs:{region}:{account}"
                ":log-group:/aws/batch/job:*",
                f"Resource::arn:aws:batch:{region}:{account}"
                ":job-definition/batch-ffmpeg-job-definition-*",
                f"Resource::arn:aws:ssm:{region}:{account}"
                f":parameter/batch-ffmpeg/*",
                "Action::s3:Abort*",
                "Action::s3:DeleteObject*",
                "Action::s3:List*",
                "Action::s3:GetBucket*",
                "Action::s3:GetObject*",
                "Resource::<bucket43879C71.Arn>/*",
                "Resource::<batchffmpegbucketD97EE012.Arn>/*",
                "Resource::arn:aws:s3:::<batchffmpegbucketD97EE012>/*",
                "Resource::*",
            ],
        ),
        {"id": "AwsSolutions-COG4", "reason": "API Gateway secured by IAM"},
        {"id": "AwsSolutions-S1", "reason": "Regression in Sidney"},
    ],
)
Aspects.of(app).add(
    cdk_nag.AwsSolutionsChecks(log_ignores=True, verbose=True, reports=True)
)
