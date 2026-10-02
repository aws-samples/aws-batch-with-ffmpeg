from aws_cdk import Stack
from aws_cdk import aws_ec2 as ec2
from aws_cdk import aws_iam as iam
from aws_cdk import Environment
from aws_cdk import aws_s3 as s3
from aws_cdk import aws_ecr as ecr
from constructs import Construct
from typing import List, Dict
from infrastructure.constructs.batch_constructs import BatchJobConstruct
from infrastructure.config.batch_config import (
    PROCESSOR_CONFIGS,
    S3FILES_ACCESS_POINT_ID_PARAMETER,
    S3FILES_FILE_SYSTEM_ID_PARAMETER,
    S3FILES_NFS_PORT,
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
    definitions for various processor types including GPU, CPU, and ARM
    instances.
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
        shared_fs_enabled: bool = False,
        **kwargs,
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)

        self.vpc = vpc
        self.s3_bucket = s3_bucket
        self.ecr_repository = ecr_repository
        self.shared_fs_enabled = shared_fs_enabled
        self._deploy_env: Environment = kwargs.get("env")

        self.security_group = self.create_security_group()
        self.instance_role = self.create_instance_role()
        self.job_role = self.create_job_role()
        self.execution_role = self.create_execution_role()

        self._batch_jobs: Dict[str, BatchJob] = {}
        for processor_name in PROCESSOR_CONFIGS.keys():
            self._batch_jobs[processor_name] = self.create_batch_job(processor_name)

        # Retain the JobDefinition cross-stack exports during migration.
        # api-stack no longer imports these (it uses the deterministic job
        # definition name), but a single `cdk deploy --all` deploys this
        # producer stack before api-stack; without retaining the exports,
        # CloudFormation refuses to delete them while the still-deployed
        # api-stack imports them ("Cannot delete export ... in use").
        # TODO: remove once all environments have been redeployed decoupled.
        for job in self._batch_jobs.values():
            self.export_value(job.job_definition.job_definition_arn)

    def create_security_group(self) -> ec2.SecurityGroup:
        security_group = ec2.SecurityGroup(
            self,
            "BatchSecurityGroup",
            vpc=self.vpc,
            description="Security group for AWS Batch FFMPEG workers",
            # Egress is scoped below instead of left open. allow_all_outbound
            # permits every port and protocol; the workers only ever need
            # HTTPS to the AWS service endpoints and NFS to the Amazon S3 Files
            # mount targets. Narrowing to those two closes the arbitrary
            # outbound path a compromised ffmpeg job would use for SSRF or data
            # exfiltration. The subnets are PRIVATE_ISOLATED with no NAT and no
            # internet gateway, so the 443 rule reaches only the in-VPC
            # interface endpoints and the S3 gateway endpoint prefix list, never
            # the internet; a CIDR rule cannot express the S3 prefix list
            # without importing the gateway endpoint cross-stack, and the
            # isolated topology already bounds where 443 can go.
            allow_all_outbound=False,
        )
        security_group.add_egress_rule(
            peer=ec2.Peer.any_ipv4(),
            connection=ec2.Port.tcp(443),
            description="HTTPS to AWS service endpoints (ECR including image layers via S3, S3, Logs, STS, SSM, X-Ray); the isolated subnets have no internet route",
        )
        # The S3 Files mount targets live in the storage stack: peering their
        # security group here would create a cross-stack cycle (the batch stack
        # already depends on landing-zone and storage). The VPC CIDR is the
        # narrowest peer expressible without that cycle, the same choice the
        # storage stack makes for the mount-target ingress rule.
        security_group.add_egress_rule(
            peer=ec2.Peer.ipv4(self.vpc.vpc_cidr_block),
            connection=ec2.Port.tcp(S3FILES_NFS_PORT),
            description="Amazon S3 Files NFS mount port",
        )
        return security_group

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
            inline_policies={
                # The user data of the compute environment hosts resolves the
                # coordinates of the Amazon S3 Files file system from these two
                # parameters at boot. The ARNs are built from the deterministic
                # parameter names rather than from the StringParameter objects:
                # those live in the storage stack and referencing them would
                # recreate the cross-stack import this decoupling removes.
                "get-s3files-parameters": iam.PolicyDocument(
                    statements=[
                        iam.PolicyStatement(
                            actions=["ssm:GetParameter"],
                            resources=[
                                self.format_arn(
                                    service="ssm",
                                    resource="parameter",
                                    resource_name=parameter_name.lstrip("/"),
                                )
                                for parameter_name in (
                                    S3FILES_FILE_SYSTEM_ID_PARAMETER,
                                    S3FILES_ACCESS_POINT_ID_PARAMETER,
                                )
                            ],
                        )
                    ]
                ),
                # Client permissions of the mount helper. The file system is
                # created in the storage stack and naming it here would import
                # its identifier, so the resource stays a wildcard scoped to
                # this account and Region; the file system policy is what
                # restricts the mount to the access point. ClientRootAccess is
                # deliberately not granted: the access point enforces the POSIX
                # identity of the containers.
                "mount-s3files": iam.PolicyDocument(
                    statements=[
                        iam.PolicyStatement(
                            actions=[
                                "s3files:ClientMount",
                                "s3files:ClientWrite",
                            ],
                            resources=[
                                self.format_arn(
                                    service="s3files",
                                    resource="file-system",
                                    resource_name="*",
                                )
                            ],
                        )
                    ]
                ),
            },
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
                            ],
                            resources=[
                                f"arn:aws:ssm:{self._deploy_env.region}:{self._deploy_env.account}"
                                f":parameter/batch-ffmpeg/*",
                                f"arn:aws:ssm:{self._deploy_env.region}:{self._deploy_env.account}"
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
            shared_fs_enabled=self.shared_fs_enabled,
            env=self._deploy_env,
        )

        return BatchJob(
            job_queue=batch_job_construct.job_queue,
            job_definition=batch_job_construct.job_definition,
            compute_environment=batch_job_construct.compute_environment,
            processor_name=processor_name,
        )
