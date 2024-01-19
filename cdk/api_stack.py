# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0
import os
import time

import aws_cdk as cdk
from aws_cdk import Stack
from aws_cdk import aws_apigateway as apig
from aws_cdk import aws_fsx as fsx
from aws_cdk import aws_iam as iam
from aws_cdk import aws_logs as cwlogs
from aws_cdk import aws_stepfunctions as sfn
from constructs import Construct

from cdk.constructs.video_batch_job import VideoBatchJob

VideoBatchJobs = list[VideoBatchJob]


class ApiStack(Stack):
    """API Gateway of the solution."""

    _region = os.environ.get("CDK_DEPLOY_REGION", os.environ["CDK_DEFAULT_REGION"])
    _account = os.environ.get("CDK_DEPLOY_ACCOUNT", os.environ["CDK_DEFAULT_ACCOUNT"])

    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        video_batch_jobs: VideoBatchJobs,
        lustre_fs: fsx.LustreFileSystem,
        sfn_state_machine: sfn.IStateMachine,
        ssm_document,
        **kwargs,
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)

        api_role = iam.Role(
            self,
            "RestAPIRole",
            assumed_by=iam.ServicePrincipal("apigateway.amazonaws.com"),
        )

        api = apig.RestApi(
            self,
            "api-batch-ffmpeg",
            rest_api_name="api-batch-ffmpeg",
            description="FFMPEG managed by AWS Batch",
            deploy_options=apig.StageOptions(
                metrics_enabled=True,
                caching_enabled=True,
                cache_data_encrypted=True,
                logging_level=apig.MethodLoggingLevel.INFO,
                tracing_enabled=True,
                access_log_destination=apig.LogGroupLogDestination(
                    cwlogs.LogGroup(self, "prod-api-logs")
                ),
            ),
        )

        api_resource_batch = api.root.add_resource("batch")
        self._api_batch_submit(api, api_resource_batch, api_role, video_batch_jobs)
        self._api_batch_describe(api, api_resource_batch, api_role)

        api_resource_sfn = api.root.add_resource("state")
        self._api_sfn_execute(api, api_resource_sfn, api_role, sfn_state_machine)
        self._api_sfn_describe(api, api_resource_sfn, api_role, sfn_state_machine)
        # api_resource_storage_task = api.root.add_resource("storage").add_resource("task")
        # self._api_fsx_release(api, api_resource_storage_task, api_role, lustre_fs)
        # self._api_fsx_describe(api, api_resource_storage_task, api_role, lustre_fs)
        # self._api_ssm_preload(api, api_resource_storage_task, api_role, ssm_document)

        cdk.CfnOutput(
            self,
            "batch-ffmpeg-api",
            export_name="ffmpeg-batch-api",
            value=api.url,
            description="FFMPEG Batch API",
        )
        cdk.CfnOutput(
            self,
            "batch-ffmpeg-api-id",
            export_name="ffmpeg-batch-api-id",
            value=api.rest_api_id,
            description="FFMPEG Batch API-id",
        )

    def _api_batch_describe(
        self, api: apig.RestApi, api_resource: apig.IResource, api_role: iam.IRole
    ):
        api_role.add_to_policy(
            iam.PolicyStatement(actions=["batch:DescribeJobs"], resources=["*"])
        )

        # AWS Integation
        request_model = api.add_model(
            "request-model-batch-describe",
            content_type="application/json",
            schema=apig.JsonSchema(
                schema=apig.JsonSchemaVersion.DRAFT4,
                title="batch-describe-request-schema",
                type=apig.JsonSchemaType.OBJECT,
                properties={
                    "jobId": apig.JsonSchema(type=apig.JsonSchemaType.STRING),
                },
            ),
        )
        integration_request_mapping_template = """
            {
                "jobs": [$input.json('$.jobId')]
            }
        """
        integration_response_mapping_template = """
        {
            "status":$input.json('$.jobs[0].status'),
            "jobId":$input.json('$.jobs[0].jobId'),
            "jobName":$input.json('$.jobs[0].jobName')
        }
        """
        integration_response = apig.IntegrationResponse(
            status_code="200",
            response_templates={
                "application/json": integration_response_mapping_template
            },
        )

        api_integration_options = apig.IntegrationOptions(
            credentials_role=api_role,
            integration_responses=[integration_response],
            request_templates={
                "application/json": integration_request_mapping_template
            },
            passthrough_behavior=apig.PassthroughBehavior.NEVER,
            request_parameters={
                "integration.request.header.Content-Type": "'application/x-www-form-urlencoded'"
            },
        )
        api_integration = apig.AwsIntegration(
            service="batch",
            integration_http_method="POST",
            path="v1/describejobs",
            options=api_integration_options,
        )

        method_response = apig.MethodResponse(
            status_code="200",
        )
        api_resource_describe = api_resource.add_resource("describe")
        api_resource_describe.add_method(
            "POST",
            integration=api_integration,
            method_responses=[method_response],
            authorization_type=apig.AuthorizationType.IAM,
            request_models={"application/json": request_model},
            request_parameters=None,
            request_validator=apig.RequestValidator(
                self,
                "batch-describe-body-validator",
                rest_api=api,
                validate_request_body=True,
                validate_request_parameters=True,
            ),
        )

    def _api_batch_submit(
        self,
        api: apig.RestApi,
        api_resource: apig.IResource,
        api_role: iam.IRole,
        video_batch_jobs: VideoBatchJobs,
    ):
        api_role.add_to_policy(
            iam.PolicyStatement(
                actions=["batch:SubmitJob"],
                resources=[
                    f"arn:aws:batch:{self._region}:{self._account}"
                    f":job-definition/batch-ffmpeg-job-definition-*",
                    f"arn:aws:batch:{self._region}:{self._account}"
                    f":job-queue/batch-ffmpeg-job-queue-*",
                ],
            )
        )

        today = time.strftime("%Y%m%d-%H%M%S")
        # FFMPEG: API Models

        request_model_submit = api.add_model(
            "request-model-batch-submit",
            content_type="application/json",
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
        # AWS Integation
        integration_response = apig.IntegrationResponse(
            status_code="200",
        )

        method_response = apig.MethodResponse(
            status_code="200",
        )
        # API Resources
        api_resource_execute = api_resource.add_resource("execute")
        for video_batch_job in video_batch_jobs:
            velocity_template_submit = f"""
            {{
                "jobName":"api-{video_batch_job.proc_name}-ffmpeg-{today}",
                "jobQueue":"{video_batch_job.job_queue_name}",
                "jobDefinition":"{video_batch_job.job_definition_name}",
                "parameters":$input.json('$')
                #set($instance = $input.json('$.instance_type'))
                #if( $instance !='""' )
                    ,
                    "nodeOverrides":
                    {{
                        "nodePropertyOverrides": [
                        {{
                            "targetNodes":"0,n",
                            "containerOverrides":
                            {{
                                "instanceType": $instance
                            }}
                        }}]
                    }}
                #end
            }}
            """

            api_integration_options_submit = apig.IntegrationOptions(
                credentials_role=api_role,
                integration_responses=[integration_response],
                request_templates={"application/json": velocity_template_submit},
                passthrough_behavior=apig.PassthroughBehavior.NEVER,
                request_parameters={
                    "integration.request.header.Content-Type": "'application/x-www-form-urlencoded'"
                },
            )

            api_integration_submit = apig.AwsIntegration(
                service="batch",
                integration_http_method="POST",
                path="v1/submitjob",
                options=api_integration_options_submit,
            )

            api_resource_proc = api_resource_execute.add_resource(
                video_batch_job.proc_name
            )

            api_resource_proc.add_method(
                "POST",
                integration=api_integration_submit,
                method_responses=[method_response],
                authorization_type=apig.AuthorizationType.IAM,
                request_models={"application/json": request_model_submit},
                request_parameters=None,
                request_validator=apig.RequestValidator(
                    self,
                    video_batch_job.proc_name + "-body-validator",
                    rest_api=api,
                    validate_request_body=True,
                    validate_request_parameters=True,
                ),
            )

    # https://docs.aws.amazon.com/step-functions/latest/apireference/API_StartExecution.html
    def _api_sfn_execute(
        self,
        api: apig.RestApi,
        api_resource: apig.IResource,
        api_role: iam.IRole,
        sfn_state_machine: sfn.IStateMachine,
    ):
        api_role.add_to_policy(
            iam.PolicyStatement(
                actions=["states:StartExecution"],
                resources=[f"{sfn_state_machine.state_machine_arn}"],
            )
        )

        request_model = api.add_model(
            "sfn-request-model",
            content_type="application/json",
            schema=apig.JsonSchema(
                schema=apig.JsonSchemaVersion.DRAFT4,
                title="sfn-request-schema",
                type=apig.JsonSchemaType.OBJECT,
                properties={
                    "name": apig.JsonSchema(type=apig.JsonSchemaType.STRING),
                    "compute": apig.JsonSchema(type=apig.JsonSchemaType.STRING),
                    "input": apig.JsonSchema(
                        type=apig.JsonSchemaType.OBJECT,
                        properties={
                            "s3_bucket": apig.JsonSchema(
                                type=apig.JsonSchemaType.STRING
                            ),
                            "s3_prefix": apig.JsonSchema(
                                type=apig.JsonSchemaType.STRING
                            ),
                            "file_options": apig.JsonSchema(
                                type=apig.JsonSchemaType.STRING
                            ),
                        },
                    ),
                    "output": apig.JsonSchema(
                        type=apig.JsonSchemaType.OBJECT,
                        properties={
                            "s3_bucket": apig.JsonSchema(
                                type=apig.JsonSchemaType.STRING
                            ),
                            "s3_prefix": apig.JsonSchema(
                                type=apig.JsonSchemaType.STRING
                            ),
                            "file_options": apig.JsonSchema(
                                type=apig.JsonSchemaType.STRING
                            ),
                        },
                    ),
                    "global": apig.JsonSchema(
                        type=apig.JsonSchemaType.OBJECT,
                        properties={
                            "options": apig.JsonSchema(type=apig.JsonSchemaType.STRING)
                        },
                    ),
                },
            ),
        )
        time.strftime("%Y%m%d-%H%M%S")
        integration_request_mapping_template = f"""
            #set($data = $util.escapeJavaScript($input.json('$')))
            {{
                "input": "$data",
                "stateMachineArn": "{sfn_state_machine.state_machine_arn}"
              }}
          """
        integration_response_mapping_template = """
          {
              "executionArn":$input.json('$.executionArn')
          }
          """
        integration_response = apig.IntegrationResponse(
            status_code="200",
            response_templates={
                "application/json": integration_response_mapping_template
            },
        )

        api_integration_options = apig.IntegrationOptions(
            credentials_role=api_role,
            integration_responses=[integration_response],
            request_templates={
                "application/json": integration_request_mapping_template
            },
            passthrough_behavior=apig.PassthroughBehavior.NEVER,
            request_parameters={
                "integration.request.header.Content-Type": "'application/x-www-form-urlencoded'"
            },
        )

        # https://docs.aws.amazon.com/fr_fr/step-functions/latest/dg/tutorial-api-gateway.html
        api_integration = apig.AwsIntegration(
            service="states",
            action="StartExecution",
            options=api_integration_options,
        )
        # Step Function API
        method_response = apig.MethodResponse(
            status_code="200",
        )
        api_resource_execute = api_resource.add_resource("execute")
        api_resource_execute.add_method(
            "POST",
            integration=api_integration,
            method_responses=[method_response],
            authorization_type=apig.AuthorizationType.IAM,
            request_models={"application/json": request_model},
            request_parameters=None,
            request_validator=apig.RequestValidator(
                self,
                "sfn-execution-body-validator",
                rest_api=api,
                validate_request_body=True,
                validate_request_parameters=True,
            ),
        )

    # https://docs.aws.amazon.com/step-functions/latest/apireference/API_DescribeExecution.html
    def _api_sfn_describe(
        self,
        api: apig.RestApi,
        api_resource: apig.IResource,
        api_role: iam.IRole,
        sfn_state_machine,
    ):
        api_role.add_to_policy(
            iam.PolicyStatement(
                actions=["states:DescribeExecution"],
                resources=[
                    f"arn:aws:states:{self._region}:{self._account}:execution:{sfn_state_machine.state_machine_name}:*"
                ],
            )
        )

        # AWS Integation
        request_model = api.add_model(
            "request-model-sfn-describe",
            content_type="application/json",
            schema=apig.JsonSchema(
                schema=apig.JsonSchemaVersion.DRAFT4,
                title="sfn-describe-request-schema",
                type=apig.JsonSchemaType.OBJECT,
                properties={
                    "executionArn": apig.JsonSchema(type=apig.JsonSchemaType.STRING),
                },
            ),
        )
        integration_request_mapping_template = """
            {
                "executionArn": $input.json('$.executionArn')
            }
        """
        integration_response_mapping_template = """
        {
            "status":$input.json('$.status'),
            "executionArn":$input.json('$.executionArn'),
            "name":$input.json('$.name')
        }
        """
        integration_response = apig.IntegrationResponse(
            status_code="200",
            response_templates={
                "application/json": integration_response_mapping_template
            },
        )

        api_integration_options = apig.IntegrationOptions(
            credentials_role=api_role,
            integration_responses=[integration_response],
            request_templates={
                "application/json": integration_request_mapping_template
            },
            passthrough_behavior=apig.PassthroughBehavior.NEVER,
            request_parameters={
                "integration.request.header.Content-Type": "'application/x-www-form-urlencoded'"
            },
        )
        api_integration = apig.AwsIntegration(
            service="states",
            action="DescribeExecution",
            options=api_integration_options,
        )

        method_response = apig.MethodResponse(
            status_code="200",
        )
        api_resource_describe = api_resource.add_resource("describe")
        api_resource_describe.add_method(
            "POST",
            integration=api_integration,
            method_responses=[method_response],
            authorization_type=apig.AuthorizationType.IAM,
            request_models={"application/json": request_model},
            request_parameters=None,
            request_validator=apig.RequestValidator(
                self,
                "sfn-describe-body-validator",
                rest_api=api,
                validate_request_body=True,
                validate_request_parameters=True,
            ),
        )

    # https://docs.aws.amazon.com/fsx/latest/APIReference/API_CreateDataRepositoryTask.html
    # BUG Waiting : API Gateway - Integration Request - AWS Service - FSx (Issue: BPL-71543)
    # def _api_fsx_release(
    #     self,
    #     api: apig.RestApi,
    #     api_resource: apig.IResource,
    #     api_role: iam.IRole,
    #     lustre_fs: fsx.LustreFileSystem,
    # ):
    #     api_role.add_to_policy(
    #         iam.PolicyStatement(
    #             actions=["fsx:CreateDataRepositoryTask"],
    #             resources=[
    #                 f"arn:aws:fsx:{self._region}:{self._account}:file-system/{lustre_fs.file_system_id}:*"
    #             ],
    #         )
    #     )
    #
    #     # AWS Integation
    #     request_model = api.add_model(
    #         "fsx-release-request-model",
    #         content_type="application/json",
    #         schema=apig.JsonSchema(
    #             schema=apig.JsonSchemaVersion.DRAFT4,
    #             title="fsx-release-request-schema",
    #             type=apig.JsonSchemaType.OBJECT,
    #             properties={
    #                 "path": apig.JsonSchema(type=apig.JsonSchemaType.STRING),
    #             },
    #         ),
    #     )
    #     integration_request_mapping_template = f"""
    #         {{
    #             "FileSystemId": "{lustre_fs.file_system_id}",
    #             "Paths": [$input.json('$.path')],
    #             "Type": "RELEASE_DATA_FROM_FILESYSTEM"
    #         }}
    #     """
    #     integration_response_mapping_template = """
    #     {
    #         "status":$input.json('$.Status'),
    #         "taskId":$input.json('$.TaskId'),
    #         "type":$input.json('$.Type')
    #     }
    #     """
    #     integration_response = apig.IntegrationResponse(
    #         status_code="200",
    #         response_templates={
    #             "application/json": integration_response_mapping_template
    #         },
    #     )
    #
    #     api_integration_options = apig.IntegrationOptions(
    #         credentials_role=api_role,
    #         integration_responses=[integration_response],
    #         request_templates={
    #             "application/json": integration_request_mapping_template
    #         },
    #         passthrough_behavior=apig.PassthroughBehavior.NEVER,
    #         request_parameters={
    #             "integration.request.header.Content-Type": "'application/x-www-form-urlencoded'"
    #         },
    #     )
    #     api_integration = apig.AwsIntegration(
    #         service="fsx",
    #         action="CreateDataRepositoryTask",
    #         options=api_integration_options,
    #     )
    #
    #     method_response = apig.MethodResponse(
    #         status_code="200",
    #     )
    #     api_resource_describe = api_resource.add_resource("release")
    #     api_resource_describe.add_method(
    #         "POST",
    #         integration=api_integration,
    #         method_responses=[method_response],
    #         authorization_type=apig.AuthorizationType.IAM,
    #         request_models={"application/json": request_model},
    #         request_parameters=None,
    #         request_validator=apig.RequestValidator(
    #             self,
    #             "fsx-release-body-validator",
    #             rest_api=api,
    #             validate_request_body=True,
    #             validate_request_parameters=True,
    #         ),
    #     )

    # https://docs.aws.amazon.com/fsx/latest/APIReference/API_DescribeDataRepositoryTasks.html
    # BUG Waiting : API Gateway - Integration Request - AWS Service - FSx (Issue: BPL-71543)
    # def _api_fsx_describe(
    #     self,
    #     api: apig.RestApi,
    #     api_resource: apig.IResource,
    #     api_role: iam.IRole,
    #     lustre_fs: fsx.LustreFileSystem,
    # ):
    #     api_role.add_to_policy(
    #         iam.PolicyStatement(
    #             actions=["fsx:DescribeDataRepositoryTasks"],
    #             resources=[
    #                 f"arn:aws:fsx:{self._region}:{self._account}:file-system/{lustre_fs.file_system_id}:*"
    #             ],
    #         )
    #     )
    #
    #     # AWS Integation
    #     request_model = api.add_model(
    #         "fsx-describe-request-model",
    #         content_type="application/json",
    #         schema=apig.JsonSchema(
    #             schema=apig.JsonSchemaVersion.DRAFT4,
    #             title="fsx-describe-request-schema",
    #             type=apig.JsonSchemaType.OBJECT,
    #             properties={
    #                 "taskId": apig.JsonSchema(type=apig.JsonSchemaType.STRING),
    #             },
    #         ),
    #     )
    #     integration_request_mapping_template = f"""
    #         {{
    #             "TaskIds": [$input.json('$.taskId')]
    #         }}
    #     """
    #     integration_response_mapping_template = """
    #     {
    #         "status":$input.json('$.Status'),
    #         "taskId":$input.json('$.TaskId'),
    #         "type":$input.json('$.Type')
    #     }
    #     """
    #     integration_response = apig.IntegrationResponse(
    #         status_code="200",
    #         response_templates={
    #             "application/json": integration_response_mapping_template
    #         },
    #     )
    #
    #     api_integration_options = apig.IntegrationOptions(
    #         credentials_role=api_role,
    #         integration_responses=[integration_response],
    #         request_templates={
    #             "application/json": integration_request_mapping_template
    #         },
    #         passthrough_behavior=apig.PassthroughBehavior.NEVER,
    #         request_parameters={
    #             "integration.request.header.Content-Type": "'application/x-www-form-urlencoded'"
    #         },
    #     )
    #     api_integration = apig.AwsIntegration(
    #         service="fsx",
    #         action="DescribeDataRepositoryTasks",
    #         options=api_integration_options,
    #     )
    #
    #     method_response = apig.MethodResponse(
    #         status_code="200",
    #     )
    #     api_resource_describe = api_resource.add_resource("describe")
    #     api_resource_describe.add_method(
    #         "POST",
    #         integration=api_integration,
    #         method_responses=[method_response],
    #         authorization_type=apig.AuthorizationType.IAM,
    #         request_models={"application/json": request_model},
    #         request_parameters=None,
    #         request_validator=apig.RequestValidator(
    #             self,
    #             "fsx-describe-body-validator",
    #             rest_api=api,
    #             validate_request_body=True,
    #             validate_request_parameters=True,
    #         ),
    #     )

    # BUG Waiting API Gateway - Integration Request - AWS Service - System Manager (Issue: BPL-71545)
    # https://docs.aws.amazon.com/systems-manager/latest/APIReference/API_GetAutomationExecution.html
    # def _api_ssm_preload(
    #     self,
    #     api: apig.RestApi,
    #     api_resource: apig.IResource,
    #     api_role: iam.IRole,
    #     ssm_document,
    # ):
    #     print("wait")
