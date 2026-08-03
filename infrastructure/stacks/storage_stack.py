import aws_cdk as cdk
import logging
import os
from aws_cdk import Stack, RemovalPolicy
from aws_cdk import aws_s3 as s3
from aws_cdk import aws_ec2 as ec2
from aws_cdk import aws_ecr as ecr
from aws_cdk import aws_iam as iam
from aws_cdk import aws_s3files as s3files
from aws_cdk import aws_ssm as ssm
from constructs import Construct
from typing import Optional

from infrastructure.config.batch_config import (
    S3FILES_ACCESS_POINT_ID_PARAMETER,
    S3FILES_FILE_SYSTEM_ID_PARAMETER,
    S3FILES_NFS_PORT,
    S3FILES_POSIX_GID,
    S3FILES_POSIX_UID,
)

LOGLEVEL = os.environ.get("LOGLEVEL", "INFO").upper()
logging.basicConfig(level=LOGLEVEL)
logger = logging.getLogger()
logger.setLevel(LOGLEVEL)


class StorageStack(Stack):
    def __init__(
        self, scope: Construct, construct_id: str, vpc: ec2.IVpc, **kwargs
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)

        self.vpc = vpc
        self.s3_bucket = self.create_s3_bucket()
        self.ecr_repository = self.create_ecr_repository()
        self.s3files_file_system = self.create_s3files_filesystem()
        self.add_outputs()

    def create_s3_bucket(self) -> s3.Bucket:
        # Versioning is a prerequisite of Amazon S3 Files, which relies on
        # object versions to synchronize the file system with the bucket.
        return s3.Bucket(
            self,
            "Bucket",
            encryption=s3.BucketEncryption.S3_MANAGED,
            enforce_ssl=True,
            versioned=True,
            block_public_access=s3.BlockPublicAccess.BLOCK_ALL,
            removal_policy=RemovalPolicy.RETAIN,
        )

    def create_ecr_repository(self) -> ecr.Repository:
        return ecr.Repository(
            self,
            "Registry",
            repository_name="batch-ffmpeg",
            image_scan_on_push=True,
            encryption=ecr.RepositoryEncryption.AES_256,
            removal_policy=RemovalPolicy.DESTROY,
            empty_on_delete=True,
        )

    def create_s3files_filesystem(self) -> Optional[s3files.CfnFileSystem]:
        """Create an Amazon S3 Files file system on the data bucket if enabled.

        The file system provisions no storage of its own: it exposes the
        objects of the bucket as files over NFS, which is what removes the
        permanently provisioned capacity the FSx for Lustre scratch cluster
        used to bill (see doc/architecture/0006).

        Returns:
            Optional[s3files.CfnFileSystem]: The created file system, or None
                if the feature is not enabled.
        """
        if not self.shared_fs_enabled():
            return None

        logging.info("Creating an Amazon S3 Files file system")

        sync_role = self.create_s3files_sync_role()
        file_system = s3files.CfnFileSystem(
            self,
            "S3FilesFileSystem",
            # `Bucket` takes the ARN of the bucket, not its name.
            bucket=self.s3_bucket.bucket_arn,
            role_arn=sync_role.role_arn,
            # The file system is scoped to the whole bucket, so the mount point
            # mirrors the S3 keys the FFmpeg wrapper builds its paths from.
            # Acknowledging the bucket warning keeps the creation
            # non-interactive, which a CI deployment requires.
            accept_bucket_warning=True,
        )

        self.create_s3files_mount_targets(file_system)
        access_point = self.create_s3files_access_point(file_system)
        self.create_s3files_file_system_policy(file_system, access_point)

        # Publish the coordinates of the file system under deterministic names.
        # The hosts that mount it resolve these parameters at boot, so no other
        # stack has to import an attribute of this file system: CloudFormation
        # refuses to update an export that is in use, which is what blocks any
        # replacement of the file system.
        ssm.StringParameter(
            self,
            "S3FilesFileSystemIdParameter",
            parameter_name=S3FILES_FILE_SYSTEM_ID_PARAMETER,
            string_value=file_system.attr_file_system_id,
            description="Identifier of the Amazon S3 Files file system",
        )
        ssm.StringParameter(
            self,
            "S3FilesAccessPointIdParameter",
            parameter_name=S3FILES_ACCESS_POINT_ID_PARAMETER,
            string_value=access_point.attr_access_point_id,
            description="Identifier of the Amazon S3 Files access point",
        )

        return file_system

    def shared_fs_enabled(self) -> bool:
        """Return whether the shared file system is enabled by context.

        Context passed via `--context key=value` arrives as a string ("true"/
        "false"), while cdk.json provides a native JSON boolean. Both are
        normalized so that the feature stays disabled by default and only
        enables on a truthy value.

        Returns:
            bool: True when the shared file system must be created.
        """
        enabled = self.node.try_get_context("batch-ffmpeg:shared-fs:enable")
        if isinstance(enabled, str):
            return enabled.strip().lower() == "true"
        return bool(enabled)

    def create_s3files_sync_role(self) -> iam.Role:
        """Create the IAM role Amazon S3 Files assumes to synchronize the
        bucket.

        Returns:
            iam.Role: The role passed as `RoleArn` of the file system.
        """
        role = iam.Role(
            self,
            "S3FilesSyncRole",
            description="AWS Batch with FFMPEG : Amazon S3 Files data synchronization",
            assumed_by=iam.ServicePrincipal("elasticfilesystem.amazonaws.com"),
        )
        role.add_to_policy(
            iam.PolicyStatement(
                actions=["s3:ListBucket*"],
                resources=[self.s3_bucket.bucket_arn],
            )
        )
        role.add_to_policy(
            iam.PolicyStatement(
                actions=[
                    "s3:AbortMultipartUpload",
                    "s3:DeleteObject",
                    "s3:GetObject*",
                    "s3:List*",
                    "s3:PutObject*",
                ],
                resources=[self.s3_bucket.arn_for_objects("*")],
            )
        )
        # Amazon S3 Files creates EventBridge rules prefixed
        # "DO-NOT-DELETE-S3-Files" to detect the objects written directly in the
        # bucket and import them on the file system.
        role.add_to_policy(
            iam.PolicyStatement(
                actions=[
                    "events:DeleteRule",
                    "events:DisableRule",
                    "events:EnableRule",
                    "events:PutRule",
                    "events:PutTargets",
                    "events:RemoveTargets",
                ],
                resources=[
                    self.format_arn(
                        service="events",
                        region="*",
                        account="*",
                        resource="rule",
                        resource_name="DO-NOT-DELETE-S3-Files*",
                    )
                ],
                conditions={
                    "StringEquals": {
                        "events:ManagedBy": "elasticfilesystem.amazonaws.com"
                    }
                },
            )
        )
        role.add_to_policy(
            iam.PolicyStatement(
                actions=[
                    "events:DescribeRule",
                    "events:ListRuleNamesByTarget",
                    "events:ListRules",
                    "events:ListTargetsByRule",
                ],
                resources=[
                    self.format_arn(
                        service="events",
                        region="*",
                        account="*",
                        resource="rule",
                        resource_name="*",
                    )
                ],
            )
        )
        return role

    def create_s3files_mount_targets(
        self, file_system: s3files.CfnFileSystem
    ) -> list[s3files.CfnMountTarget]:
        """Create one mount target per isolated subnet.

        A client can only mount through a mount target located in its own
        Availability Zone, and the compute environments spread over every
        isolated subnet, so every isolated subnet gets one.

        Args:
            file_system (s3files.CfnFileSystem): The file system to expose.

        Returns:
            list[s3files.CfnMountTarget]: The created mount targets.
        """
        security_group = ec2.SecurityGroup(
            self,
            "S3FilesSecurityGroup",
            vpc=self.vpc,
            description="Security group for the Amazon S3 Files mount targets",
            allow_all_outbound=True,
        )
        # The compute environments live in another stack: peering their security
        # group here would make the storage stack depend on the batch stack,
        # which already depends on this one. The VPC CIDR is the narrowest peer
        # expressible without that cycle.
        security_group.add_ingress_rule(
            peer=ec2.Peer.ipv4(self.vpc.vpc_cidr_block),
            connection=ec2.Port.tcp(S3FILES_NFS_PORT),
            description="Amazon S3 Files NFS client port",
        )

        mount_targets = []
        for index, subnet in enumerate(
            self.vpc.select_subnets(subnet_type=ec2.SubnetType.PRIVATE_ISOLATED).subnets
        ):
            mount_targets.append(
                s3files.CfnMountTarget(
                    self,
                    f"S3FilesMountTarget{index}",
                    file_system_id=file_system.attr_file_system_id,
                    subnet_id=subnet.subnet_id,
                    security_groups=[security_group.security_group_id],
                )
            )
        return mount_targets

    def create_s3files_access_point(
        self, file_system: s3files.CfnFileSystem
    ) -> s3files.CfnAccessPoint:
        """Create the access point enforcing the POSIX identity of the
        containers.

        The FFmpeg containers run as uid 1000, and the access point attributes
        every file system operation to that identity, so the files they write
        are theirs instead of root's.

        Args:
            file_system (s3files.CfnFileSystem): The file system to expose.

        Returns:
            s3files.CfnAccessPoint: The created access point.
        """
        return s3files.CfnAccessPoint(
            self,
            "S3FilesAccessPoint",
            file_system_id=file_system.attr_file_system_id,
            posix_user=s3files.CfnAccessPoint.PosixUserProperty(
                uid=S3FILES_POSIX_UID,
                gid=S3FILES_POSIX_GID,
            ),
            # The wrapper resolves its input and output paths from the S3 keys,
            # so the root of the access point is the root of the file system.
            root_directory=s3files.CfnAccessPoint.RootDirectoryProperty(path="/"),
        )

    def create_s3files_file_system_policy(
        self,
        file_system: s3files.CfnFileSystem,
        access_point: s3files.CfnAccessPoint,
    ) -> s3files.CfnFileSystemPolicy:
        """Restrict client access to mounts going through the access point.

        Without this policy a client of the account could mount the root of the
        file system directly and bypass the POSIX identity the access point
        enforces.

        Args:
            file_system (s3files.CfnFileSystem): The file system to protect.
            access_point (s3files.CfnAccessPoint): The only allowed access point.

        Returns:
            s3files.CfnFileSystemPolicy: The created file system policy.
        """
        return s3files.CfnFileSystemPolicy(
            self,
            "S3FilesFileSystemPolicy",
            file_system_id=file_system.attr_file_system_id,
            policy=iam.PolicyDocument(
                statements=[
                    iam.PolicyStatement(
                        principals=[iam.AccountRootPrincipal()],
                        actions=["s3files:ClientMount", "s3files:ClientWrite"],
                        conditions={
                            "StringEquals": {
                                "s3files:AccessPointArn": access_point.attr_access_point_arn
                            }
                        },
                    )
                ]
            ),
        )

    def add_outputs(self) -> None:
        """Add CloudFormation outputs for the created resources."""
        cdk.CfnOutput(
            self,
            "DataBucketName",
            value=self.s3_bucket.bucket_name,
            description="Name of the S3 bucket for data storage",
            key="DataBucketName",
        )

        cdk.CfnOutput(
            self,
            "ECRRepositoryName",
            value=self.ecr_repository.repository_name,
            description="Name of the ECR repository for FFmpeg container images",
            key="ECRRepositoryName",
        )

        if self.s3files_file_system:
            cdk.CfnOutput(
                self,
                "S3FilesFileSystemId",
                value=self.s3files_file_system.attr_file_system_id,
                description="Identifier of the Amazon S3 Files file system",
                key="S3FilesFileSystemId",
            )
