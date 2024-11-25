from aws_cdk import Stack
from aws_cdk import aws_ec2 as ec2
from aws_cdk import aws_iam as iam
from aws_cdk import Environment
from aws_cdk import aws_s3 as s3
from aws_cdk import aws_ecr as ecr
from aws_cdk import aws_fsx as fsx
from constructs import Construct
from typing import List, Dict, Optional
from infrastructure.constructs.batch_constructs import BatchJobConstruct
from infrastructure.config.batch_config import (
    PROCESSOR_CONFIGS,
)


class BatchJob:
    def __init__(self, job_queue, job_definition, compute_environment, processor_name):
        self.job_queue = job_queue
        self.job_definition = job_definition
        self.compute_environment = compute_environment
        self.processor_name = processor_name

    @property
    def job_queue_name(self):
        return self.job_queue.job_queue_name

    @property
    def job_definition_name(self):
        return self.job_definition.job_definition_name


class BatchProcessingStack(Stack):
    """A stack that sets up AWS Batch resources for video processing.

    This stack creates compute environments, job queues, and job
    definitions for various processor types including GPU, CPU, ARM, and
    Xilinx instances.
    """

    @property
    def batch_jobs(self) -> List[BatchJob]:
        return list(self._batch_jobs.values())

    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        vpc: ec2.IVpc,
        s3_bucket: s3.IBucket,
        ecr_repository: ecr.IRepository,
        lustre_fs: Optional[fsx.LustreFileSystem] = None,
        **kwargs,
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)

        self.vpc = vpc
        self.s3_bucket = s3_bucket
        self.ecr_repository = ecr_repository
        self.lustre_fs = lustre_fs
        self.env: Environment = kwargs.get("env")

        self.security_group = self.create_security_group()
        self.instance_role = self.create_instance_role()
        self.job_role = self.create_job_role()
        self.execution_role = self.create_execution_role()

        self._batch_jobs: Dict[str, BatchJob] = {}
        for processor_name in PROCESSOR_CONFIGS.keys():
            self._batch_jobs[processor_name] = self.create_batch_job(processor_name)

    def create_security_group(self) -> ec2.SecurityGroup:
        return ec2.SecurityGroup(
            self,
            "BatchSecurityGroup",
            vpc=self.vpc,
            description="Security group for AWS Batch FFMPEG workers",
            allow_all_outbound=True,
        )

    def create_instance_role(self) -> iam.Role:
        role = iam.Role(
            self,
            "BatchInstanceRole",
            assumed_by=iam.CompositePrincipal(
                iam.ServicePrincipal("ec2.amazonaws.com"),
                iam.ServicePrincipal("ecs.amazonaws.com"),
                iam.ServicePrincipal("ecs-tasks.amazonaws.com"),
            ),
            managed_policies=[
                iam.ManagedPolicy.from_aws_managed_policy_name(
                    "service-role/AmazonEC2ContainerServiceforEC2Role"
                ),
                iam.ManagedPolicy.from_aws_managed_policy_name(
                    "AWSXrayWriteOnlyAccess"
                ),
            ],
        )
        self.s3_bucket.grant_read_write(role)
        return role

    def create_job_role(self) -> iam.Role:
        role = iam.Role(
            self,
            "BatchJobRole",
            assumed_by=iam.CompositePrincipal(
                iam.ServicePrincipal("ecs.amazonaws.com"),
                iam.ServicePrincipal("ecs-tasks.amazonaws.com"),
            ),
            managed_policies=[
                iam.ManagedPolicy.from_aws_managed_policy_name(
                    "service-role/AmazonECSTaskExecutionRolePolicy"
                ),
                iam.ManagedPolicy.from_aws_managed_policy_name(
                    "AWSXrayWriteOnlyAccess"
                ),
            ],
            inline_policies={
                "get-ssm-parameters": iam.PolicyDocument(
                    statements=[
                        iam.PolicyStatement(
                            actions=[
                                "ssm:GetParameters",
                                "ssm:GetParameter",
                                "ssm:GetParametersByPath",
                                "secretsmanager:GetSecretValue",
                                "kms:Decrypt",
                            ],
                            resources=[
                                f"arn:aws:ssm:{self.env.region}:{self.env.account}"
                                f":parameter/batch-ffmpeg/*",
                                f"arn:aws:ssm:{self.env.region}:{self.env.account}"
                                f":parameter/batch-ffmpeg",
                            ],
                        )
                    ]
                )
            },
        )
        self.s3_bucket.grant_read_write(role)
        return role

    def create_execution_role(self) -> iam.Role:
        return iam.Role(
            self,
            "BatchExecutionRole",
            assumed_by=iam.CompositePrincipal(
                iam.ServicePrincipal("ecs.amazonaws.com"),
                iam.ServicePrincipal("ecs-tasks.amazonaws.com"),
            ),
            managed_policies=[
                iam.ManagedPolicy.from_aws_managed_policy_name(
                    "service-role/AmazonECSTaskExecutionRolePolicy"
                ),
                iam.ManagedPolicy.from_aws_managed_policy_name(
                    "AWSXrayWriteOnlyAccess"
                ),
            ],
        )

    def create_batch_job(self, processor_name: str):
        batch_job_construct = BatchJobConstruct(
            self,
            f"BatchJob-{processor_name}",
            processor_name=processor_name,
            vpc=self.vpc,
            security_group=self.security_group,
            s3_bucket=self.s3_bucket,
            ecr_repository=self.ecr_repository,
            instance_role=self.instance_role,
            execution_role=self.execution_role,
            job_role=self.job_role,
            lustre_fs=self.lustre_fs,
            env=self.env,
        )

        return BatchJob(
            job_queue=batch_job_construct.job_queue,
            job_definition=batch_job_construct.job_definition,
            compute_environment=batch_job_construct.compute_environment,
            processor_name=processor_name,
        )
