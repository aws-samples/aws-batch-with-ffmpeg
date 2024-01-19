# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0
import os

import aws_cdk as cdk
from aws_cdk import Duration, Stack
from aws_cdk import aws_events as events
from aws_cdk import aws_events_targets as targets
from aws_cdk import aws_glue as cfn_glue
from aws_cdk import aws_glue_alpha as glue
from aws_cdk import aws_iam as iam
from aws_cdk import aws_lambda as faas
from aws_cdk import aws_s3 as s3
from aws_cdk import aws_ssm as ssm
from constructs import Construct
from from_root import from_root


class MetricsStack(Stack):
    """Export traces and quality metrics on Amazon S3 with Athena."""

    def __init__(
        self, scope: Construct, construct_id: str, s3_bucket: s3.IBucket, **kwargs
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # Parameter to activate video quality metrics
        ssm.StringParameter(
            self,
            "quality-metrics-flag",
            allowed_pattern="TRUE|FALSE",
            description="Enable FFMPEG quality metrics calculation in the AWS BATCH FFMPEG Stack",
            parameter_name="/batch-ffmpeg/ffqm",
            string_value="FALSE",
        )

        # Lambda
        handler = faas.Function(
            self,
            "metrics",
            description="Export X-Ray traces, start Glue Crawler, Create/ update Athena views",
            code=faas.Code.from_asset(str(from_root("application", "dist_lambda.zip"))),
            handler="metrics_lambda.export_handler",
            timeout=Duration.seconds(600),
            runtime=faas.Runtime.PYTHON_3_11,
            runtime_management_mode=faas.RuntimeManagementMode.AUTO,
            environment=dict(S3_BUCKET=s3_bucket.bucket_name),
        )
        cdk.CfnOutput(
            self,
            "batch-ffmpeg-lambda-metrics-arn",
            export_name="batch-ffmpeg-lambda-metrics-arn",
            value=handler.function_arn,
            description="AWS Batch with FFmpeg : Lambda Metrics ARN",
        )

        s3_bucket.grant_write(handler)
        self.handler = handler

        # Event Bridge Cron
        events.Rule(
            self,
            "schedule",
            schedule=events.Schedule.cron(minute="0", hour="8-20/2", week_day="2-6"),
            targets=[targets.LambdaFunction(handler)],
        )

        # Glue database
        database = glue.Database(self, "database", database_name="aws_batch_ffmpeg")

        # IAM
        region = os.environ.get("CDK_DEPLOY_REGION", os.environ["CDK_DEFAULT_REGION"])
        account = os.environ.get(
            "CDK_DEPLOY_ACCOUNT", os.environ["CDK_DEFAULT_ACCOUNT"]
        )
        xray_policy = iam.PolicyStatement(
            actions=["xray:BatchGetTraces", "xray:GetTraceSummaries"], resources=["*"]
        )
        glue_policies = [
            iam.PolicyStatement(
                actions=["glue:GetDatabase", "glue:GetDatabases"],
                resources=[
                    f"arn:aws:glue:{region}:{account}:catalog",
                    f"arn:aws:glue:{region}:{account}:database/{database.database_name}",
                ],
            ),
            iam.PolicyStatement(
                actions=["glue:GetTables", "glue:GetTable", "glue:GetPartitions"],
                resources=[
                    f"arn:aws:glue:{region}:{account}:catalog",
                    f"arn:aws:glue:{region}:{account}:database/{database.database_name}",
                ],
            ),
            iam.PolicyStatement(
                actions=["athena:StartQueryExecution"],
                resources=[f"arn:aws:athena:{region}:{account}:workgroup/primary"],
            ),
            iam.PolicyStatement(
                actions=["glue:StartCrawler", "glue:GetCrawler"],
                resources=[
                    f"arn:aws:glue:{region}:{account}:crawler/aws_batch_ffmpeg_crawler"
                ],
            ),
        ]
        s3_policy = iam.PolicyStatement(
            actions=[
                "s3:GetBucketLocation",
                "s3:GetObject",
                "s3:ListBucket",
                "s3:ListBucketMultipartUploads",
                "s3:ListMultipartUploadParts",
                "s3:AbortMultipartUpload",
                "s3:CreateBucket",
                "s3:PutObject",
            ],
            resources=[
                f"arn:aws:s3:::{s3_bucket.bucket_name}",
                f"arn:aws:s3:::{s3_bucket.bucket_name}/*",
            ],
        )
        handler.role.attach_inline_policy(
            iam.Policy(self, "xray-read-traces", statements=[xray_policy])
        )
        handler.role.attach_inline_policy(
            iam.Policy(self, "glue-crawler", statements=glue_policies)
        )
        handler.role.attach_inline_policy(
            iam.Policy(self, "athena-s3", statements=[s3_policy])
        )

        # Glue crawler IAM
        glue_managed_policy = "arn:aws:iam::aws:policy/service-role/AWSGlueServiceRole"
        glue_service_url = "glue.amazonaws.com"

        crawler_role = iam.Role(
            self,
            "crawler-role",
            managed_policies=[
                iam.ManagedPolicy.from_managed_policy_arn(
                    self, "glue", managed_policy_arn=glue_managed_policy
                )
            ],
            assumed_by=iam.ServicePrincipal(service=glue_service_url),
        )
        s3_bucket.grant_read(crawler_role)

        crawler = cfn_glue.CfnCrawler(
            self,
            "crawler",
            role=crawler_role.role_name,
            database_name=database.database_name,
            name="aws_batch_ffmpeg_crawler",
            table_prefix="batch_ffmpeg_",
            recrawl_policy=cfn_glue.CfnCrawler.RecrawlPolicyProperty(
                recrawl_behavior="CRAWL_EVERYTHING"
            ),
            configuration='{"Version": 1.0,"CrawlerOutput": { "Partitions": { "AddOrUpdateBehavior": "InheritFromTable" }}}',
            targets=cfn_glue.CfnCrawler.TargetsProperty(
                s3_targets=[
                    cfn_glue.CfnCrawler.S3TargetProperty(
                        path=f"s3://{s3_bucket.bucket_name}/metrics/xray/"
                    ),
                    cfn_glue.CfnCrawler.S3TargetProperty(
                        path=f"s3://{s3_bucket.bucket_name}/metrics/ffqm/"
                    ),
                ]
            ),
            schema_change_policy=cfn_glue.CfnCrawler.SchemaChangePolicyProperty(
                delete_behavior="LOG", update_behavior="UPDATE_IN_DATABASE"
            ),
        )
        crawler.node.add_dependency(database)
