# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0
import time
import os
import aws_cdk as cdk
from constructs import Construct
from aws_cdk import (
    Stack,
    aws_iam as iam,
    aws_apigateway as apig,
    aws_logs as cwlogs,
)
from cdk.constructs.video_batch_job import VideoBatchJob

VideoBatchJobs = list[VideoBatchJob]


class ApiStack(Stack):
    """API Gateway of the solution"""

    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        video_batch_jobs: VideoBatchJobs,
        metrics_handler,
        **kwargs,
    ) -> None:

        super().__init__(scope, construct_id, **kwargs)

        api = apig.RestApi(
            self,
            "api-batch-ffmpeg",
            rest_api_name="api-batch-ffmpeg",
            description="FFMPEG managed by AWS Batch",
            deploy_options=apig.StageOptions(
                metrics_enabled=True,
                logging_level=apig.MethodLoggingLevel.INFO,
                tracing_enabled=True,
                access_log_destination=apig.LogGroupLogDestination(
                    cwlogs.LogGroup(self, "prod-api-logs")
                ),
            ),
        )
        # API Models
        ffmpeg_request_model = api.add_model(
            "ffmpeg-request-model",
            content_type="application/json",
            model_name="FfmpegRequest",
            schema=apig.JsonSchema(
                schema=apig.JsonSchemaVersion.DRAFT4,
                title="ffmpeg-request-schema",
                type=apig.JsonSchemaType.OBJECT,
                properties={
                    "global_options": apig.JsonSchema(type=apig.JsonSchemaType.STRING),
                    "input_file_options": apig.JsonSchema(
                        type=apig.JsonSchemaType.STRING
                    ),
                    "output_file_options": apig.JsonSchema(
                        type=apig.JsonSchemaType.STRING
                    ),
                    "output_url": apig.JsonSchema(type=apig.JsonSchemaType.STRING),
                    "name": apig.JsonSchema(type=apig.JsonSchemaType.STRING),
                    "instance_type": apig.JsonSchema(type=apig.JsonSchemaType.STRING),
                },
            ),
        )
        batch_response_model = api.add_model(
            "ffmpeg-response-model",
            content_type="application/json",
            model_name="BatchResponse",
            schema=apig.JsonSchema(
                schema=apig.JsonSchemaVersion.DRAFT4,
                title="ffmpeg-response-schema",
                type=apig.JsonSchemaType.OBJECT,
                properties={
                    "job_id": apig.JsonSchema(type=apig.JsonSchemaType.STRING),
                },
            ),
        )

        api_role = iam.Role(
            self,
            "RestAPIRole",
            assumed_by=iam.ServicePrincipal("apigateway.amazonaws.com"),
            inline_policies={
                "batch-submit-job": iam.PolicyDocument(
                    statements=[
                        iam.PolicyStatement(
                            actions=["batch:SubmitJob"],
                            resources=[
                                f"arn:aws:batch:{os.getenv('CDK_DEFAULT_REGION')}:{os.getenv('CDK_DEFAULT_ACCOUNT')}"
                                f":job-definition/batch-ffmpeg-job-definition-*",
                                f"arn:aws:batch:{os.getenv('CDK_DEFAULT_REGION')}:{os.getenv('CDK_DEFAULT_ACCOUNT')}"
                                f":job-queue/batch-ffmpeg-job-queue-*",
                            ],
                        )
                    ]
                )
            },
        )

        # AWS Integation

        integration_response = apig.IntegrationResponse(
            status_code="200",
        )

        batch_method_response = apig.MethodResponse(
            status_code="200",
        )
        video_tool = "ffmpeg"
        for video_batch_job in video_batch_jobs:

            today = time.strftime("%Y%m%d-%H%M%S")
            velocity_template = "{"
            velocity_template += (
                '"jobName":"api-'
                + video_batch_job.type
                + "-"
                + video_tool
                + "-"
                + today
                + '",\n'
            )
            velocity_template += (
                '"jobQueue":"' + video_batch_job.job_queue_name + '",\n'
            )
            velocity_template += (
                '"jobDefinition":"' + video_batch_job.job_definition_name + '",\n'
            )
            velocity_template += "\"parameters\":$input.json('$')\n"
            velocity_template += '#set($instance = $input.json(\'$.instance_type\')) \n \
#if( $instance !=\'""\' ) \
,\
"nodeOverrides":{ \
    "nodePropertyOverrides": [ \
    { \
        "targetNodes":"0,n", \
        "containerOverrides": { \
            "instanceType": $instance \
        } \
    }] \
} \
#end \
}'

            api_integration_options = apig.IntegrationOptions(
                credentials_role=api_role,
                integration_responses=[integration_response],
                request_templates={"application/json": velocity_template},
                passthrough_behavior=apig.PassthroughBehavior.NEVER,
                request_parameters={
                    "integration.request.header.Content-Type": "'application/x-www-form-urlencoded'"
                },
            )
            api_integration = apig.AwsIntegration(
                service="batch",
                integration_http_method="POST",
                path="v1/submitjob",
                options=api_integration_options,
            )

            # API Resources
            proc_type = api.root.add_resource(video_batch_job.type)
            command = proc_type.add_resource(video_tool)

            command.add_method(
                "POST",
                integration=api_integration,
                method_responses=[batch_method_response],
                authorization_type=apig.AuthorizationType.IAM,
                request_models={"application/json": ffmpeg_request_model},
                request_validator=apig.RequestValidator(
                    self,
                    video_batch_job.type + "-body-validator",
                    rest_api=api,
                    validate_request_body=True,
                ),
            )

        # Quality metrics
        api_integration = apig.LambdaIntegration(
            metrics_handler,
            request_templates={"application/json": '{"statusCode":"200"}'},
        )
        metrics = api.root.add_resource("metrics")
        metrics_export = metrics.add_resource("export")
        metrics_export.add_method(
            "GET", api_integration, authorization_type=apig.AuthorizationType.IAM
        )

        cdk.CfnOutput(
            self,
            "ffmpegbatchapi",
            export_name="ffmpeg-batch-api",
            value=api.url,
            description="FFMPEG Batch API",
        )
