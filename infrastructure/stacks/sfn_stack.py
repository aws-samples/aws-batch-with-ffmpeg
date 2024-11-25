import json
from aws_cdk import Stack, CfnOutput
from aws_cdk import aws_iam as iam
from aws_cdk import aws_logs as logs
from aws_cdk import aws_s3 as s3
from aws_cdk import aws_stepfunctions as sfn
import aws_cdk as cdk
from constructs import Construct
import from_root


class SfnStack(Stack):
    """A stack that sets up an AWS Step Functions state machine for executing
    AWS Batch with FFmpeg jobs.

    This stack creates a Step Functions state machine that processes a
    list of S3 objects using AWS Batch jobs with FFmpeg. It includes the
    necessary IAM roles and permissions, as well as logging
    configuration for the state machine.
    """

    def __init__(
        self, scope: Construct, construct_id: str, s3_bucket: s3.IBucket, **kwargs
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)

        self.s3_bucket = s3_bucket
        self.state_role = self.create_state_machine_role()
        self.log_group = self.create_log_group()
        self.state_machine = self.create_state_machine()

    def create_state_machine_role(self) -> iam.Role:
        """Create and return the IAM role for the Step Functions state
        machine."""
        role = iam.Role(
            self,
            "StepFunctionsRole",
            assumed_by=iam.ServicePrincipal("states.amazonaws.com"),
            description="IAM Role used by AWS Step Functions for FFMPEG batch processing",
        )

        role.add_managed_policy(
            iam.ManagedPolicy.from_aws_managed_policy_name("AWSXrayWriteOnlyAccess")
        )

        role.add_to_policy(
            iam.PolicyStatement(
                actions=[
                    "batch:SubmitJob",
                    "batch:DescribeJobs",
                    "batch:TerminateJob",
                ],
                resources=["*"],
            )
        )

        role.add_to_policy(
            iam.PolicyStatement(
                actions=[
                    "events:PutTargets",
                    "events:PutRule",
                    "events:DescribeRule",
                ],
                resources=[
                    f"arn:aws:events:{self.region}:{self.account}:rule/StepFunctionsGetEventsForBatchJobsRule"
                ],
            )
        )

        role.add_to_policy(
            iam.PolicyStatement(
                actions=[
                    "states:StartExecution",
                    "states:DescribeExecution",
                    "states:StopExecution",
                ],
                resources=[
                    f"arn:aws:states:{self.region}:{self.account}:stateMachine:batch-ffmpeg-state-machine",
                    f"arn:aws:states:{self.region}:{self.account}:execution:batch-ffmpeg-state-machine:*",
                ],
            )
        )

        self.s3_bucket.grant_read_write(role)

        return role

    def create_log_group(self) -> logs.LogGroup:
        """Create and return the CloudWatch log group for the state machine."""
        return logs.LogGroup(
            self,
            "StepFunctionsLogGroup",
            log_group_name=f"/aws/vendedlogs/states/batch-ffmpeg-{self.stack_name}",
            retention=logs.RetentionDays.ONE_WEEK,
            removal_policy=cdk.RemovalPolicy.DESTROY,
        )

    def create_state_machine(self) -> sfn.StateMachine:
        """Create and return the Step Functions state machine."""
        definition = self.load_state_machine_definition()

        state_machine = sfn.StateMachine(
            self,
            "FFmpegStateMachine",
            definition_body=sfn.DefinitionBody.from_string(definition),
            role=self.state_role,
            logs=sfn.LogOptions(destination=self.log_group, level=sfn.LogLevel.ALL),
            tracing_enabled=True,
            state_machine_name="batch-ffmpeg-state-machine",
        )

        CfnOutput(
            self,
            "StateMachineArn",
            value=state_machine.state_machine_arn,
            description="ARN of the FFmpeg Batch Processing State Machine",
        )

        return state_machine

    def load_state_machine_definition(self) -> str:
        """Load and return the state machine definition from a JSON file.

        Returns:
            str: The state machine definition as a JSON string.
        """
        file_path = from_root.from_root(
            "infrastructure", "stacks", "state-machine", "main_state.asl.json"
        )
        with open(file_path, "r") as f:
            definition = json.load(f)

        # Perform string replacements
        definition_str = json.dumps(definition)
        replacements = {
            "${REGION}": self.region,
            "${ACCOUNT}": self.account,
        }
        for key, value in replacements.items():
            definition_str = definition_str.replace(key, value)

        return definition_str
