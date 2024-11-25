import os
import aws_cdk as cdk
from aws_cdk import Stack, Duration
from aws_cdk import aws_events as events
from aws_cdk import aws_events_targets as targets
from aws_cdk import aws_glue as glue
from aws_cdk import aws_glue_alpha as glue_alpha
from aws_cdk import aws_iam as iam
from aws_cdk import aws_lambda as lmb
from aws_cdk import aws_s3 as s3
from aws_cdk import aws_ssm as ssm
from constructs import Construct
from aws_cdk.aws_logs import RetentionDays
from from_root import from_root


class MetricsStack(Stack):
    """A stack that sets up infrastructure for exporting and analyzing metrics.

    This stack creates resources for exporting X-Ray traces, running
    Glue crawlers, and creating/updating Athena views. It also sets up a
    Lambda function to handle these tasks and schedules it to run
    periodically.
    """

    GLUE_DATABASE_NAME = "batch_ffmpeg"
    GLUE_CRAWLER_NAME = "batch_ffmpeg_crawler"
    GLUE_TABLE_PREFIX = "batch_ffmpeg_"

    def __init__(
        self, scope: Construct, construct_id: str, s3_bucket: s3.IBucket, **kwargs
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)

        self.s3_bucket = s3_bucket

        self.create_ssm_parameter()
        self.lambda_role = self.create_lambda_role()
        self.lambda_function = self.create_lambda_function()
        self.create_glue_resources()
        self.create_event_rule()

    def create_ssm_parameter(self) -> None:
        """Create SSM parameter to control FFMPEG quality metrics
        calculation."""
        ssm.StringParameter(
            self,
            "QualityMetricsFlag",
            allowed_pattern="TRUE|FALSE",
            description="Enable FFMPEG quality metrics calculation in the AWS BATCH FFMPEG Stack",
            parameter_name="/batch-ffmpeg/ffqm",
            string_value="FALSE",
        )

    def create_lambda_function(self) -> lmb.Function:
        """Create Lambda function for exporting metrics and managing
        Glue/Athena resources."""
        function = lmb.Function(
            self,
            "MetricsExportFunction",
            description="Export X-Ray traces, start Glue Crawler, Create/ update Athena views",
            runtime=lmb.Runtime.PYTHON_3_13,
            runtime_management_mode=lmb.RuntimeManagementMode.AUTO,
            handler="metrics.metrics_lambda.export_handler",
            code=lmb.Code.from_asset(os.path.join(from_root("src", "dist_lambda.zip"))),
            timeout=Duration.minutes(10),
            memory_size=256,
            environment={
                "S3_BUCKET": self.s3_bucket.bucket_name,
                "GLUE_DATABASE_NAME": "batch_ffmpeg",
                "GLUE_CRAWLER_NAME": "batch_ffmpeg_crawler",
            },
            retry_attempts=2,
            role=self.lambda_role,
            log_retention=RetentionDays.ONE_WEEK,
        )

        self.s3_bucket.grant_read_write(function)

        cdk.CfnOutput(
            self,
            "MetricsExportLambdaArn",
            value=function.function_arn,
            description="ARN of the Lambda function for metrics export",
            key="MetricsExportLambdaArn",
        )

        return function

    def create_lambda_role(self) -> iam.Role:
        """Create and return an IAM role for the Lambda function."""
        role = iam.Role(
            self,
            "MetricsLambdaRole",
            assumed_by=iam.ServicePrincipal("lambda.amazonaws.com"),
            description="Role for Metrics Export Lambda function",
        )

        role.add_managed_policy(
            iam.ManagedPolicy.from_aws_managed_policy_name(
                "service-role/AWSLambdaBasicExecutionRole"
            )
        )

        role.add_to_policy(
            iam.PolicyStatement(
                actions=["xray:BatchGetTraces", "xray:GetTraceSummaries"],
                resources=["*"],
            )
        )
        glue_policies = [
            iam.PolicyStatement(
                actions=["glue:GetDatabase", "glue:GetDatabases"],
                resources=[
                    f"arn:aws:glue:{self.region}:{self.account}:catalog",
                    f"arn:aws:glue:{self.region}:{self.account}:database/{self.GLUE_DATABASE_NAME}",
                ],
            ),
            iam.PolicyStatement(
                actions=[
                    "glue:GetTables",
                    "glue:CreateTable",
                    "glue:GetTable",
                    "glue:GetPartitions",
                    "glue:UpdateTable",
                ],
                resources=[
                    f"arn:aws:glue:{self.region}:{self.account}:catalog",
                    f"arn:aws:glue:{self.region}:{self.account}:database/{self.GLUE_DATABASE_NAME}",
                    f"arn:aws:glue:{self.region}:{self.account}:database/{self.GLUE_DATABASE_NAME}/*",
                    f"arn:aws:glue:{self.region}:{self.account}:table/{self.GLUE_DATABASE_NAME}/*",
                ],
            ),
            iam.PolicyStatement(
                actions=["athena:StartQueryExecution", "athena:GetQueryExecution"],
                resources=[
                    f"arn:aws:athena:{self.region}:{self.account}:workgroup/primary"
                ],
            ),
            iam.PolicyStatement(
                actions=["glue:StartCrawler", "glue:GetCrawler"],
                resources=[
                    f"arn:aws:glue:{self.region}:{self.account}:crawler/{self.GLUE_CRAWLER_NAME}"
                ],
            ),
        ]

        role.attach_inline_policy(
            iam.Policy(self, "glue-policies", statements=glue_policies)
        )

        self.s3_bucket.grant_read_write(role)

        return role

    def create_glue_resources(self) -> None:
        """Create Glue database and crawler for metrics data."""
        glue_alpha.Database(
            self,
            "GlueDatabase",
            database_name=self.GLUE_DATABASE_NAME,
        )

        crawler_role = iam.Role(
            self,
            "GlueCrawlerRole",
            assumed_by=iam.ServicePrincipal("glue.amazonaws.com"),
            managed_policies=[
                iam.ManagedPolicy.from_aws_managed_policy_name(
                    "service-role/AWSGlueServiceRole"
                )
            ],
        )
        self.s3_bucket.grant_read(crawler_role)

        glue.CfnCrawler(
            self,
            "GlueCrawler",
            role=crawler_role.role_arn,
            database_name=self.GLUE_DATABASE_NAME,
            name=self.GLUE_CRAWLER_NAME,
            table_prefix=self.GLUE_TABLE_PREFIX,
            targets=glue.CfnCrawler.TargetsProperty(
                s3_targets=[
                    glue.CfnCrawler.S3TargetProperty(
                        path=f"s3://{self.s3_bucket.bucket_name}/metrics/xray/"
                    ),
                    glue.CfnCrawler.S3TargetProperty(
                        path=f"s3://{self.s3_bucket.bucket_name}/metrics/ffqm/"
                    ),
                ]
            ),
            schema_change_policy=glue.CfnCrawler.SchemaChangePolicyProperty(
                delete_behavior="LOG", update_behavior="UPDATE_IN_DATABASE"
            ),
            recrawl_policy=glue.CfnCrawler.RecrawlPolicyProperty(
                recrawl_behavior="CRAWL_EVERYTHING"
            ),
        )

    def create_event_rule(self) -> None:
        """Create EventBridge rule to trigger the Lambda function
        periodically."""
        events.Rule(
            self,
            "MetricsExportSchedule",
            schedule=events.Schedule.cron(
                minute="0", hour="8-20/2", week_day="MON-FRI"
            ),
            targets=[targets.LambdaFunction(self.lambda_function)],
        )
