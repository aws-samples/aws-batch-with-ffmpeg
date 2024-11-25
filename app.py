#!/usr/bin/env python3
# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0
"""Main CDK application file for the AWS Batch with FFmpeg solution.

This script defines and synthesizes all the stacks required for the AWS
Batch with FFmpeg solution, including networking, storage, batch
processing, metrics, state machine, and API resources.
"""

import os
from typing import Dict

import aws_cdk as cdk
import aws_cdk.aws_servicecatalogappregistry_alpha as appreg
import cdk_nag
from aws_cdk import Aspects, Environment, Tags

from infrastructure.stacks.api_stack import ApiStack
from infrastructure.stacks.batch_processing_stack import BatchProcessingStack
from infrastructure.stacks.landing_zone_stack import LandingZoneStack
from infrastructure.stacks.metrics_stack import MetricsStack
from infrastructure.stacks.sfn_stack import SfnStack
from infrastructure.stacks.storage_stack import StorageStack


def get_environment() -> Environment:
    """Get the AWS environment for deployment.

    Returns:
        Environment: The AWS environment configuration.
    """
    account = os.environ.get("CDK_DEPLOY_ACCOUNT", os.environ["CDK_DEFAULT_ACCOUNT"])
    region = os.environ.get("CDK_DEPLOY_REGION", os.environ["CDK_DEFAULT_REGION"])
    return Environment(account=account, region=region)


def create_app() -> cdk.App:
    """Create and configure the CDK application.

    Returns:
        cdk.App: The configured CDK application.
    """
    app = cdk.App()
    Tags.of(app).add("application", "batch-ffmpeg")
    return app


def create_stacks(app: cdk.App, env: Environment) -> Dict[str, cdk.Stack]:
    stacks = {}

    stacks["landing_zone"] = LandingZoneStack(
        app,
        "batch-ffmpeg-landing-stack",
        env=env,
        description="AWS Batch with FFmpeg: Networking",
    )

    stacks["storage"] = StorageStack(
        app,
        "batch-ffmpeg-storage-stack",
        vpc=stacks["landing_zone"].vpc,
        env=env,
        description="AWS Batch with FFmpeg: Storage",
    )

    stacks["batch"] = BatchProcessingStack(
        app,
        "batch-ffmpeg-stack",
        vpc=stacks["landing_zone"].vpc,
        s3_bucket=stacks["storage"].s3_bucket,
        ecr_repository=stacks["storage"].ecr_repository,
        lustre_fs=stacks["storage"].lustre_fs,
        env=env,
        description="AWS Batch with FFmpeg: Main stack (uksb-1tg6b0m8t)",
    )

    stacks["metrics"] = MetricsStack(
        app,
        "batch-ffmpeg-metrics-stack",
        s3_bucket=stacks["storage"].s3_bucket,
        env=env,
        description="AWS Batch with FFmpeg: Metrics stack",
    )

    stacks["sfn"] = SfnStack(
        app,
        "batch-ffmpeg-sfn-stack",
        s3_bucket=stacks["storage"].s3_bucket,
        env=env,
        description="AWS Batch with FFmpeg: AWS Step Functions",
    )

    stacks["api"] = ApiStack(
        app,
        "batch-ffmpeg-api-stack",
        batch_jobs=stacks["batch"].batch_jobs,
        sfn_state_machine=stacks["sfn"].state_machine,
        env=env,
        description="AWS Batch with FFmpeg: API Gateway",
    )

    return stacks


def create_app_registry(
    app: cdk.App, env: Environment, stacks: Dict[str, cdk.Stack]
) -> appreg.ApplicationAssociator:
    """Create and configure the Application Registry.

    Args:
        app (cdk.App): The CDK application.
        env (Environment): The AWS environment.
        stacks (Dict[str, cdk.Stack]): The created stacks.

    Returns:
        appreg.ApplicationAssociator: The configured Application Registry.
    """
    application = appreg.ApplicationAssociator(
        app,
        "batch-ffmepg-app",
        applications=[
            appreg.TargetApplication.create_application_stack(
                application_name="batch-ffmpeg",
                description="AWS Batch with FFMPEG: Application",
                stack_name="batch-ffmpeg-application",
                env=env,
            )
        ],
    )
    for stack in stacks.values():
        application.node.add_dependency(stack)
    return application


def add_cdk_nag(app: cdk.App, env: Environment) -> None:
    """Add CDK NAG checks and suppressions.

    Args:
        app (cdk.App): The CDK application.
        env (Environment): The AWS environment.
    """
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
                    "Policy::arn:<AWS::Partition>:iam::aws:policy/service-role/AWSGlueServiceRole",
                    "Policy::arn:<AWS::Partition>:iam::aws:policy/service-role/AmazonEC2ContainerServiceforEC2Role",
                    "Policy::arn:<AWS::Partition>:iam::aws:policy/service-role/AmazonEC2RoleforSSM",
                    "Policy::arn:<AWS::Partition>:iam::aws:policy/AmazonSSMManagedInstanceCore",
                    "Policy::arn:<AWS::Partition>:iam::aws:policy/service-role/AmazonSSMAutomationRole",
                ],
            ),
            cdk_nag.NagPackSuppression(
                id="AwsSolutions-IAM5",
                reason="AWS Managed Service Role and AWS managed XRay Policy",
                applies_to=[
                    f"Resource::arn:aws:batch:{env.region}:{env.account}:job-queue/batch-ffmpeg-job-queue-*",
                    f"Resource::arn:<AWS::Partition>:logs:{env.region}:{env.account}:log-group:/aws/batch/job:*",
                    f"Resource::arn:aws:batch:{env.region}:{env.account}:job-definition/batch-ffmpeg-job-definition-*",
                    f"Resource::arn:aws:ssm:{env.region}:{env.account}:parameter/batch-ffmpeg/*",
                    f"Resource::arn:aws:states:{env.region}:{env.account}:execution:batch-ffmpeg-state-machine:*",
                    f"Resource::arn:aws:glue:{env.region}:{env.account}:table/batch_ffmpeg/*",
                    f"Resource::arn:aws:glue:{env.region}:{env.account}:database/batch_ffmpeg/*",
                    "Action::s3:Abort*",
                    "Action::s3:DeleteObject*",
                    "Action::s3:List*",
                    "Action::s3:GetBucket*",
                    "Action::s3:GetObject*",
                    "Resource::<bucket43879C71.Arn>/*",
                    "Resource::<batchffmpegbucketD97EE012.Arn>/*",
                    "Resource::arn:aws:s3:::<batchffmpegbucketD97EE012>/*",
                    "Resource::<Bucket83908E77.Arn>/*",
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


def main() -> None:
    """Main function to create and synthesize the CDK application."""
    env = get_environment()
    app = create_app()
    stacks = create_stacks(app, env)
    create_app_registry(app, env, stacks)
    add_cdk_nag(app, env)
    app.synth()


if __name__ == "__main__":
    main()
