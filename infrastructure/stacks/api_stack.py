from aws_cdk import Stack
import aws_cdk as cdk
from aws_cdk import aws_apigateway as apigw
from aws_cdk import aws_iam as iam
from aws_cdk import aws_stepfunctions as sfn
from aws_cdk import aws_logs as cwlogs
from constructs import Construct
from typing import List
from infrastructure.stacks.batch_processing_stack import BatchJob
import time


class ApiStack(Stack):
    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        batch_jobs: List[BatchJob],
        sfn_state_machine: sfn.IStateMachine,
        **kwargs,
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)

        self.api_role = self.create_api_role()
        self.api = self.create_api()
        self.create_batch_endpoints(batch_jobs)
        self.create_sfn_endpoints(sfn_state_machine)
        self.add_output()

    def add_output(self) -> None:
        cdk.CfnOutput(
            self,
            "ApiUrl",
            key="ApiUrl",
            value=self.api.url,
            description="FFMPEG Batch API URL",
        )
        cdk.CfnOutput(
            self,
            "FfmpegBatchApiId",
            key="ApiId",
            value=self.api.rest_api_id,
            description="FFMPEG Batch API id",
        )

        cdk.CfnOutput(
            self,
            "ApiAccessLog",
            key="ApiAccessLog",
            value=self.log_group.log_group_name,
            description="FFMPEG Batch API Access log group name",
        )
        api_log_group_name = f"API-Gateway-Execution-Logs_{self.api.rest_api_id}/{self.api.deployment_stage.stage_name}"
        cdk.CfnOutput(
            self,
            "ApiExecutionLog",
            key="ApiExecutionLog",
            value=api_log_group_name,
            description="FFMPEG Batch API Execution log group name",
        )

    def create_api_role(self) -> iam.Role:
        """Create and return an IAM role for the API Gateway."""
        role = iam.Role(
            self,
            "ApiGatewayRole",
            assumed_by=iam.ServicePrincipal("apigateway.amazonaws.com"),
            description="Role for API Gateway to access AWS services",
        )
        role.add_to_policy(
            iam.PolicyStatement(
                actions=[
                    "batch:SubmitJob",
                    "batch:DescribeJobs",
                    "states:StartExecution",
                    "states:DescribeExecution",
                ],
                resources=["*"],
            )
        )
        return role

    def create_api(self) -> apigw.RestApi:
        """Create and return the main API Gateway RestApi."""
        self.log_group = cwlogs.LogGroup(self, "api-logs")
        return apigw.RestApi(
            self,
            "FFmpegBatchApi",
            rest_api_name="api-batch-ffmpeg",
            description="FFMPEG managed by AWS Batch",
            # Defense in depth on top of the IAM authorizer on every method:
            # the resource policy restricts invocation to principals of the
            # account that owns the API. Without it, IAM auth with no resource
            # policy lets any AWS principal that its own account allows to call
            # execute-api reach the endpoint cross-account. Scope to the org
            # (aws:PrincipalOrgID) instead if the API is shared across accounts.
            policy=iam.PolicyDocument(
                statements=[
                    iam.PolicyStatement(
                        effect=iam.Effect.ALLOW,
                        principals=[iam.AnyPrincipal()],
                        actions=["execute-api:Invoke"],
                        resources=["execute-api:/*"],
                        conditions={
                            "StringEquals": {"aws:PrincipalAccount": self.account}
                        },
                    )
                ]
            ),
            deploy_options=apigw.StageOptions(
                metrics_enabled=True,
                caching_enabled=True,
                cache_data_encrypted=True,
                logging_level=apigw.MethodLoggingLevel.INFO,
                tracing_enabled=True,
                access_log_destination=apigw.LogGroupLogDestination(self.log_group),
            ),
            cloud_watch_role=True,
        )

    def create_batch_endpoints(self, batch_jobs: List[BatchJob]) -> None:
        """Create API endpoints for AWS Batch operations."""
        batch_resource = self.api.root.add_resource("batch")
        self.create_batch_submit_endpoint(batch_resource, batch_jobs)
        self.create_batch_describe_endpoint(batch_resource)

    def create_batch_submit_endpoint(
        self, batch_resource: apigw.IResource, batch_jobs: List[BatchJob]
    ) -> None:
        """Create an API endpoint for submitting AWS Batch jobs."""
        submit_resource = batch_resource.add_resource("execute")

        today = time.strftime("%Y%m%d-%H%M%S")
        # FFMPEG: API Models

        request_model_submit = self.api.add_model(
            "request-model-batch-submit",
            content_type="application/json",
            schema=apigw.JsonSchema(
                schema=apigw.JsonSchemaVersion.DRAFT4,
                title="ffmpeg-request-schema",
                type=apigw.JsonSchemaType.OBJECT,
                properties={
                    "global_options": apigw.JsonSchema(
                        type=apigw.JsonSchemaType.STRING
                    ),
                    "input_file_options": apigw.JsonSchema(
                        type=apigw.JsonSchemaType.STRING
                    ),
                    "output_file_options": apigw.JsonSchema(
                        type=apigw.JsonSchemaType.STRING
                    ),
                    "output_url": apigw.JsonSchema(type=apigw.JsonSchemaType.STRING),
                    "name": apigw.JsonSchema(type=apigw.JsonSchemaType.STRING),
                    "instance_type": apigw.JsonSchema(type=apigw.JsonSchemaType.STRING),
                },
            ),
        )
        # AWS Integation
        integration_response = apigw.IntegrationResponse(
            status_code="200",
        )

        method_response = apigw.MethodResponse(
            status_code="200",
        )

        for job in batch_jobs:
            velocity_template_submit = f"""
            {{
                "jobName":"api-{job.processor_name}-ffmpeg-{today}",
                "jobQueue":"{job.job_queue_name}",
                "jobDefinition":"batch-ffmpeg-job-definition-{job.processor_name}",
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

            integration_options_submit = apigw.IntegrationOptions(
                credentials_role=self.api_role,
                integration_responses=[integration_response],
                request_templates={"application/json": velocity_template_submit},
                passthrough_behavior=apigw.PassthroughBehavior.NEVER,
                request_parameters={
                    "integration.request.header.Content-Type": "'application/x-www-form-urlencoded'"
                },
            )

            integration_submit = apigw.AwsIntegration(
                service="batch",
                integration_http_method="POST",
                path="v1/submitjob",
                options=integration_options_submit,
            )

            proc_resource = submit_resource.add_resource(job.processor_name)

            proc_resource.add_method(
                "POST",
                integration=integration_submit,
                method_responses=[method_response],
                authorization_type=apigw.AuthorizationType.IAM,
                request_models={"application/json": request_model_submit},
                request_validator=apigw.RequestValidator(
                    self,
                    job.processor_name + "-body-validator",
                    rest_api=self.api,
                    validate_request_body=True,
                    validate_request_parameters=True,
                ),
            )

    def create_batch_describe_endpoint(self, batch_resource: apigw.IResource) -> None:
        """Create an API endpoint for describing AWS Batch jobs."""
        # AWS Integation
        request_model = self.api.add_model(
            "request-model-batch-describe",
            content_type="application/json",
            schema=apigw.JsonSchema(
                schema=apigw.JsonSchemaVersion.DRAFT4,
                title="batch-describe-request-schema",
                type=apigw.JsonSchemaType.OBJECT,
                properties={
                    "jobId": apigw.JsonSchema(type=apigw.JsonSchemaType.STRING),
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
        integration_response = apigw.IntegrationResponse(
            status_code="200",
            response_templates={
                "application/json": integration_response_mapping_template
            },
        )

        integration_options = apigw.IntegrationOptions(
            credentials_role=self.api_role,
            integration_responses=[integration_response],
            request_templates={
                "application/json": integration_request_mapping_template
            },
            passthrough_behavior=apigw.PassthroughBehavior.NEVER,
            request_parameters={
                "integration.request.header.Content-Type": "'application/x-www-form-urlencoded'"
            },
        )
        integration = apigw.AwsIntegration(
            service="batch",
            integration_http_method="POST",
            path="v1/describejobs",
            options=integration_options,
        )

        method_response = apigw.MethodResponse(
            status_code="200",
        )
        api_resource_describe = batch_resource.add_resource("describe")
        api_resource_describe.add_method(
            "POST",
            integration=integration,
            method_responses=[method_response],
            authorization_type=apigw.AuthorizationType.IAM,
            request_models={"application/json": request_model},
            request_parameters=None,
            request_validator=apigw.RequestValidator(
                self,
                "batch-describe-body-validator",
                rest_api=self.api,
                validate_request_body=True,
                validate_request_parameters=True,
            ),
        )

    def create_sfn_endpoints(self, sfn_state_machine: sfn.IStateMachine) -> None:
        """Create API endpoints for Step Functions operations."""
        sfn_resource = self.api.root.add_resource("state")
        self.create_sfn_execute_endpoint(sfn_resource, sfn_state_machine)
        self.create_sfn_describe_execution_endpoint(sfn_resource)

    def create_sfn_execute_endpoint(
        self, sfn_resource: apigw.IResource, sfn_state_machine: sfn.IStateMachine
    ) -> None:
        """Create an API endpoint for starting Step Functions executions."""
        request_model = self.api.add_model(
            "sfn-request-model",
            content_type="application/json",
            schema=apigw.JsonSchema(
                schema=apigw.JsonSchemaVersion.DRAFT4,
                title="sfn-request-schema",
                type=apigw.JsonSchemaType.OBJECT,
                properties={
                    "name": apigw.JsonSchema(type=apigw.JsonSchemaType.STRING),
                    "compute": apigw.JsonSchema(type=apigw.JsonSchemaType.STRING),
                    "input": apigw.JsonSchema(
                        type=apigw.JsonSchemaType.OBJECT,
                        properties={
                            "s3_bucket": apigw.JsonSchema(
                                type=apigw.JsonSchemaType.STRING
                            ),
                            "s3_prefix": apigw.JsonSchema(
                                type=apigw.JsonSchemaType.STRING
                            ),
                            "file_options": apigw.JsonSchema(
                                type=apigw.JsonSchemaType.STRING
                            ),
                        },
                    ),
                    "output": apigw.JsonSchema(
                        type=apigw.JsonSchemaType.OBJECT,
                        properties={
                            "s3_bucket": apigw.JsonSchema(
                                type=apigw.JsonSchemaType.STRING
                            ),
                            "s3_prefix": apigw.JsonSchema(
                                type=apigw.JsonSchemaType.STRING
                            ),
                            "file_options": apigw.JsonSchema(
                                type=apigw.JsonSchemaType.STRING
                            ),
                        },
                    ),
                    "global": apigw.JsonSchema(
                        type=apigw.JsonSchemaType.OBJECT,
                        properties={
                            "options": apigw.JsonSchema(
                                type=apigw.JsonSchemaType.STRING
                            )
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
        integration_response = apigw.IntegrationResponse(
            status_code="200",
            response_templates={
                "application/json": integration_response_mapping_template
            },
        )

        api_integration_options = apigw.IntegrationOptions(
            credentials_role=self.api_role,
            integration_responses=[integration_response],
            request_templates={
                "application/json": integration_request_mapping_template
            },
            passthrough_behavior=apigw.PassthroughBehavior.NEVER,
            request_parameters={
                "integration.request.header.Content-Type": "'application/x-www-form-urlencoded'"
            },
        )

        # https://docs.aws.amazon.com/fr_fr/step-functions/latest/dg/tutorial-api-gateway.html
        api_integration = apigw.AwsIntegration(
            service="states",
            action="StartExecution",
            options=api_integration_options,
        )
        # Step Function API
        method_response = apigw.MethodResponse(
            status_code="200",
        )
        api_resource_execute = sfn_resource.add_resource("execute")
        api_resource_execute.add_method(
            "POST",
            integration=api_integration,
            method_responses=[method_response],
            authorization_type=apigw.AuthorizationType.IAM,
            request_models={"application/json": request_model},
            request_parameters=None,
            request_validator=apigw.RequestValidator(
                self,
                "sfn-execution-body-validator",
                rest_api=self.api,
                validate_request_body=True,
                validate_request_parameters=True,
            ),
        )

    def create_sfn_describe_execution_endpoint(
        self, sfn_resource: apigw.IResource
    ) -> None:
        """Create an API endpoint for describing Step Functions executions."""
        # AWS Integation
        request_model = self.api.add_model(
            "request-model-sfn-describe",
            content_type="application/json",
            schema=apigw.JsonSchema(
                schema=apigw.JsonSchemaVersion.DRAFT4,
                title="sfn-describe-request-schema",
                type=apigw.JsonSchemaType.OBJECT,
                properties={
                    "executionArn": apigw.JsonSchema(type=apigw.JsonSchemaType.STRING),
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
        integration_response = apigw.IntegrationResponse(
            status_code="200",
            response_templates={
                "application/json": integration_response_mapping_template
            },
        )

        api_integration_options = apigw.IntegrationOptions(
            credentials_role=self.api_role,
            integration_responses=[integration_response],
            request_templates={
                "application/json": integration_request_mapping_template
            },
            passthrough_behavior=apigw.PassthroughBehavior.NEVER,
            request_parameters={
                "integration.request.header.Content-Type": "'application/x-www-form-urlencoded'"
            },
        )
        api_integration = apigw.AwsIntegration(
            service="states",
            action="DescribeExecution",
            options=api_integration_options,
        )

        method_response = apigw.MethodResponse(
            status_code="200",
        )
        api_resource_describe = sfn_resource.add_resource("describe")
        api_resource_describe.add_method(
            "POST",
            integration=api_integration,
            method_responses=[method_response],
            authorization_type=apigw.AuthorizationType.IAM,
            request_models={"application/json": request_model},
            request_parameters=None,
            request_validator=apigw.RequestValidator(
                self,
                "sfn-describe-body-validator",
                rest_api=self.api,
                validate_request_body=True,
                validate_request_parameters=True,
            ),
        )
