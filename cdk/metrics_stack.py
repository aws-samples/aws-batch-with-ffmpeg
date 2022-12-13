# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0
import os
from constructs import Construct
from aws_cdk import (
    Stack,
    aws_iam as iam,
    aws_lambda as faas,
    aws_events as events,
    aws_events_targets as targets,
    Duration,
    Stack,
    aws_glue as cfn_glue,
    aws_glue_alpha as glue,
    aws_ssm as ssm,
    aws_s3 as s3,
)

from from_root import from_root


class MetricsStack(Stack):
    """Export traces and quality metrics on Amazon S3 with Athena"""

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

        # Xray Traces Export
        with open(
            from_root("application", "metrics", "metrics_lambda.py"),
            encoding="utf8",
        ) as file:
            handler_code = file.read()

        handler = faas.Function(
            self,
            "metrics",
            code=faas.InlineCode(handler_code),
            handler="index.export_handler",
            timeout=Duration.seconds(300),
            runtime=faas.Runtime.PYTHON_3_9,
            environment=dict(S3_BUCKET=s3_bucket.bucket_name),
        )
        s3_bucket.grant_write(handler)

        xray_policy = iam.PolicyStatement(
            actions=["xray:BatchGetTraces", "xray:GetTraceSummaries"], resources=["*"]
        )
        crawler_policy = iam.PolicyStatement(
            actions=["glue:StartCrawler"],
            resources=[
                f"arn:aws:glue:{os.getenv('CDK_DEFAULT_REGION')}:{os.getenv('CDK_DEFAULT_ACCOUNT')}"
                f":crawler/aws-batch-ffmpeg-crawler"
            ],
        )
        handler.role.attach_inline_policy(
            iam.Policy(self, "xray-read-traces", statements=[xray_policy])
        )
        handler.role.attach_inline_policy(
            iam.Policy(self, "glue-crawler", statements=[crawler_policy])
        )
        self.handler = handler

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

        database = glue.Database(self, "database", database_name="aws-batch-ffmpeg")
        cfn_glue.CfnCrawler(
            self,
            "crawler",
            role=crawler_role.role_name,
            database_name=database.database_name,
            name="aws-batch-ffmpeg-crawler",
            table_prefix="batch-ffmpeg-",
            schedule=cfn_glue.CfnCrawler.ScheduleProperty(
                schedule_expression="cron(00 6-20 ? * MON-FRI *)"
            ),
            recrawl_policy=cfn_glue.CfnCrawler.RecrawlPolicyProperty(
                recrawl_behavior="CRAWL_EVERYTHING"
            ),
            configuration='{"Version": 1.0,"CrawlerOutput": { "Partitions": { "AddOrUpdateBehavior": "InheritFromTable" }}}',
            targets=cfn_glue.CfnCrawler.TargetsProperty(
                s3_targets=[
                    cfn_glue.CfnCrawler.S3TargetProperty(
                        path = f"s3://{s3_bucket.bucket_name}/metrics/xray/"
                    )
                ]
            ),
            schema_change_policy=cfn_glue.CfnCrawler.SchemaChangePolicyProperty(
                delete_behavior="LOG", update_behavior="UPDATE_IN_DATABASE"
            ),
        )
