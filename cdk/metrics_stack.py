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
    aws_athena as athena,
    aws_glue_alpha as glue,
    aws_ssm as ssm,
    aws_s3 as s3,
)
import aws_cdk as cdk
from from_root import from_root
import base64

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
                f":crawler/aws_batch_ffmpeg_crawler"
            ],
        )
        handler.role.attach_inline_policy(
            iam.Policy(self, "xray-read-traces", statements=[xray_policy])
        )
        handler.role.attach_inline_policy(
            iam.Policy(self, "glue-crawler", statements=[crawler_policy])
        )
        self.handler = handler

        # Crawler
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

        database = glue.Database(self, "database", database_name="aws_batch_ffmpeg")
        crawler = cfn_glue.CfnCrawler(
            self,
            "crawler",
            role=crawler_role.role_name,
            database_name=database.database_name,
            name="aws_batch_ffmpeg_crawler",
            table_prefix="batch_ffmpeg_",
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
        crawler.node.add_dependency(database)
        
        # Athena view
        # CREATE OR REPLACE VIEW "batch_ffmpeg_xray_flat" AS 
        # SELECT
        #   trace_id
        # , subsegment.id subsegement_id
        # , annotations.name
        # , subsegment.name subegment_name
        # , CAST(from_unixtime(start_time) AS timestamp) start_date
        # , CAST(from_unixtime(end_time) AS timestamp) end_date
        # , subsegment.start_time subsegement_start_time
        # , subsegment.end_time subsegement_end_time
        # , CAST(from_unixtime(subsegment.start_time) AS timestamp) subsegment_start_date
        # , CAST(from_unixtime(subsegment.end_time) AS timestamp) subsegment_end_date
        # , date_diff('second',CAST(from_unixtime(start_time) AS timestamp), CAST(from_unixtime(end_time) AS timestamp)) trace_duration_sec
        # , date_diff('second',CAST(from_unixtime(subsegment.start_time) AS timestamp), CAST(from_unixtime(subsegment.end_time) AS timestamp)) subsegment_duration_sec
        # , aws.ec2.instance_type
        # , annotations.aws_batch_jq_name
        # FROM
        #   (batch_ffmpeg_xray
        # CROSS JOIN UNNEST(batch_ffmpeg_xray.subsegments) t (subsegment))

        # Athena saved query
        query = athena.CfnNamedQuery(self,"named-query",
            database="aws_batch_ffmpeg",
            name="batch_ffmpeg_xray_flat",
            description="Flattening all nested arrays of the table",
            query_string='SELECT trace_id, subsegment.id as subsegement_id, annotations.name, subsegment.name as subegment_name, start_time, end_time, subsegment.start_time as subsegement_start_time, subsegment.end_time as subsegement_end_time, aws.ec2.instance_type,annotations.aws_batch_jq_name FROM batch_ffmpeg_xray CROSS JOIN UNNEST(batch_ffmpeg_xray.subsegments) AS t(subsegment)'
        )

        query.node.add_dependency(crawler)

        # Athena view
        original_text = '{'
        original_text += '"originalSql": "SELECT trace_id, subsegment.id as subsegement_id, annotations.name, subsegment.name as subegment_name, CAST(from_unixtime(start_time) AS timestamp) as start_date, CAST(from_unixtime(end_time) AS timestamp) as end_date, CAST(from_unixtime(subsegment.start_time) AS timestamp) as subsegement_start_date, CAST(from_unixtime(subsegment.end_time) AS timestamp) as subsegement_end_date , date_diff(\'second\',CAST(from_unixtime(start_time) AS timestamp), CAST(from_unixtime(end_time) AS timestamp)) trace_duration_sec, date_diff(\'second\',CAST(from_unixtime(subsegment.start_time) AS timestamp), CAST(from_unixtime(subsegment.end_time) AS timestamp)) subsegment_duration_sec, aws.ec2.instance_type,annotations.aws_batch_jq_name FROM batch_ffmpeg_xray CROSS JOIN UNNEST(batch_ffmpeg_xray.subsegments) AS t(subsegment)",'
        original_text += '"catalog":"awsdatacatalog",'
        original_text += '"schema":"aws_batch_ffmpeg",'
        original_text += '"columns":['
        original_text += '{"name":"trace_id","type":"varchar"},'
        original_text += '{"name":"subsegement_id","type":"varchar"},'
        original_text += '{"name":"annotations.name","type":"varchar"},'
        original_text += '{"name":"subegment_name","type":"varchar"},'
        original_text += '{"name":"start_date","type":"timestamp"},'
        original_text += '{"name":"end_date","type":"timestamp"},'
        original_text += '{"name":"subsegement_start_date","type":"timestamp"},'
        original_text += '{"name":"subsegement_end_date","type":"timestamp"},'
        original_text += '{"name":"trace_duraction_sec","type":"bigint"},'
        original_text += '{"name":"subsegment_duraction_sec","type":"bingint"},'
        original_text += '{"name":"aws.ec2.instance_type","type":"varchar"},'
        original_text += '{"name":"annotations.aws_batch_jq_name","type":"varchar"}'
        original_text += ']'
        original_text += '}'

        # https://stackoverflow.com/questions/56289272/create-aws-athena-view-programmatically
        original_text_base64 = base64.b64encode(original_text.encode('utf-8')).decode()
        
        view = cfn_glue.CfnTable(self,'view',
            database_name="aws_batch_ffmpeg",
            catalog_id=cdk.Stack.of(self).account,
            table_input= cfn_glue.CfnTable.TableInputProperty(
                description="Flattening all nested arrays of the table",
                name="batch_ffmpeg_xray_flat",
                table_type= "VIRTUAL_VIEW",
                view_expanded_text= "/* Presto View */",
                view_original_text= f"/* Presto View: {original_text_base64} */",
                parameters={
                    'presto_view': "true",
                    'comment': 'Presto View'
                },
                storage_descriptor= cfn_glue.CfnTable.StorageDescriptorProperty(
                    serde_info= cfn_glue.CfnTable.SerdeInfoProperty(
                        name= "JsonSerDe",
                        serialization_library = "org.openx.data.jsonserde.JsonSerDe"
                    ),
                    columns=[
                        cfn_glue.CfnTable.ColumnProperty(
                            name='trace_id',
                            type="string"
                        ),
                        cfn_glue.CfnTable.ColumnProperty(
                            name='subsegement_id',
                            type="string"
                        ),
                        cfn_glue.CfnTable.ColumnProperty(
                            name='annotations.name',
                            type="string"
                        ),
                        cfn_glue.CfnTable.ColumnProperty(
                            name='subegment_name',
                            type="string"
                        ),
                        cfn_glue.CfnTable.ColumnProperty(
                            name='start_date',
                            type="timestamp"
                        ),
                        cfn_glue.CfnTable.ColumnProperty(
                            name='end_date',
                            type="timestamp"
                        ),
                        cfn_glue.CfnTable.ColumnProperty(
                            name='subsegement_start_date',
                            type="timestamp"
                        ),
                        cfn_glue.CfnTable.ColumnProperty(
                            name='subsegement_end_date',
                            type="timestamp"
                        ),
                        cfn_glue.CfnTable.ColumnProperty(
                            name='trace_duraction_sec',
                            type="bigint"
                        ),
                        cfn_glue.CfnTable.ColumnProperty(
                            name='subsegment_duraction_sec',
                            type="bigint"
                        ),
                        cfn_glue.CfnTable.ColumnProperty(
                            name='aws.ec2.instance_type',
                            type="string"
                        ),
                        cfn_glue.CfnTable.ColumnProperty(
                            name='annotations.aws_batch_jq_name',
                            type="string"
                        ),
                    ]
                )
            )
        )
        view.node.add_dependency(crawler)


