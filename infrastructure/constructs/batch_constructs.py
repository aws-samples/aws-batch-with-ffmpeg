# batch_constructs.py

from aws_cdk import (
    aws_ec2 as ec2,
    aws_ecs as ecs,
    aws_iam as iam,
    aws_batch as batch,
    aws_s3 as s3,
    aws_ecr as ecr,
    aws_fsx as fsx,
    Duration,
    Size,
    Environment,
)
import logging
import os
from constructs import Construct
from infrastructure.config.batch_config import (
    PROCESSOR_CONFIGS,
    JOB_DEF_CPU,
    JOB_DEF_MEMORY,
    LUSTRE_MOUNT_POINT,
    FFMPEG_SCRIPT_COMMAND,
    FFMPEG_SCRIPT_DEFAULT_VALUES,
)
from from_root import from_root
import hashlib

LOGLEVEL = os.environ.get("LOGLEVEL", "INFO").upper()
logging.basicConfig(level=LOGLEVEL)
logger = logging.getLogger()
logger.setLevel(LOGLEVEL)


class BatchJobConstruct(Construct):
    """A CDK Construct for creating an AWS Batch job for video processing.

    This construct creates all necessary components for a Batch job including
    container definition, job definition, compute environment, and job queue.
    It's designed to be flexible and configurable based on the processor type.

    Attributes:
        processor_name (str): The name of the processor type for this job.
        job_queue_name (str): The name of the created job queue.
        job_definition_name (str): The name of the created job definition.
        job_queue_arn (str): The ARN of the created job queue.
        job_definition_arn (str): The ARN of the created job definition.
    """

    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        *,
        processor_name: str,
        vpc: ec2.IVpc,
        security_group: ec2.ISecurityGroup,
        s3_bucket: s3.IBucket,
        ecr_repository: ecr.IRepository,
        instance_role: iam.IRole,
        execution_role: iam.IRole,
        job_role: iam.IRole,
        lustre_fs: fsx.LustreFileSystem = None,
        env: Environment,
        **kwargs,
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)
        self.env = env
        self.processor_name = processor_name
        self.processor_config = PROCESSOR_CONFIGS[processor_name]

        self.job_queue_name = f"batch-ffmpeg-job-queue-{processor_name}"
        self.job_definition_name = f"batch-ffmpeg-job-definition-{processor_name}"

        # Create all necessary components for the Batch job
        self.create_container_definition(
            s3_bucket, ecr_repository, execution_role, job_role, lustre_fs
        )
        self.create_job_definition()
        self.create_compute_environment(vpc, security_group, instance_role, lustre_fs)
        self.create_job_queue()

    def create_container_definition(
        self, s3_bucket, ecr_repository, execution_role, job_role, lustre_fs
    ):
        # Set up basic environment variables
        job_definition_container_env = {
            "AWS_XRAY_SDK_ENABLED": "true",
            "S3_BUCKET": s3_bucket.bucket_name,
        }

        # Set up Lustre volumes if a Lustre file system is provided
        lustre_volumes = None
        if lustre_fs and self.processor_config["container_type"] == "EC2":
            job_definition_container_env["FSX_MOUNT_POINT"] = LUSTRE_MOUNT_POINT
            lustre_volumes = [
                batch.HostVolume(
                    host_path=LUSTRE_MOUNT_POINT,
                    name="fsx-lustre-vol-name",
                    container_path=LUSTRE_MOUNT_POINT,
                )
            ]

        # Prepare common arguments for container definition
        container_def_args = {
            "image": ecs.ContainerImage.from_ecr_repository(
                ecr_repository, self.processor_config["container_tag"]
            ),
            "command": FFMPEG_SCRIPT_COMMAND,
            "environment": job_definition_container_env,
            "execution_role": execution_role,
            "job_role": job_role,
            "cpu": JOB_DEF_CPU,
            "memory": Size.mebibytes(JOB_DEF_MEMORY),
            "volumes": lustre_volumes,
        }

        # Add Linux parameters if specified in the processor configuration
        if self.processor_config.get("linux_parameters"):
            linux_parameters = batch.LinuxParameters(
                self, f"{self.processor_name}-linux-param"
            )
            for device in self.processor_config["linux_parameters"]["devices"]:
                linux_parameters.add_devices(batch.Device(**device))
            container_def_args["linux_parameters"] = linux_parameters

        if self.processor_config.get("gpu"):
            container_def_args["gpu"] = self.processor_config["gpu"]
        if self.processor_config.get("privileged"):
            container_def_args["privileged"] = self.processor_config["privileged"]
        if self.processor_config.get("environment"):
            container_def_args["environment"].update(
                self.processor_config["environment"]
            )

        # Create either a Fargate or EC2 container definition based on the processor configuration
        if self.processor_config["container_type"] == "FARGATE":
            self.container_definition = batch.EcsFargateContainerDefinition(
                self,
                f"container-def-{self.processor_name}",
                **container_def_args,
                fargate_cpu_architecture=self.processor_config.get(
                    "fargate_cpu_architecture"
                ),
            )
        else:
            self.container_definition = batch.EcsEc2ContainerDefinition(
                self, f"container-def-{self.processor_name}", **container_def_args
            )

    def create_job_definition(self):
        """Create the job definition for the Batch job.

        This method sets up the job definition using the previously
        created container definition.
        """
        self.job_definition = batch.EcsJobDefinition(
            self,
            "JobDefinition",
            job_definition_name=self.job_definition_name,
            container=self.container_definition,
            parameters=FFMPEG_SCRIPT_DEFAULT_VALUES,
            retry_attempts=1,
            timeout=Duration.hours(10),
        )

    def create_launch_template(self, is_fargate, proc_name, lustre_fs):
        if not is_fargate:
            # Multipart User Data
            multipart_user_data = ec2.MultipartUserData()
            with open(
                from_root("infrastructure", "constructs", "user_data_xray.txt")
            ) as f:
                user_data_xray_txt = f.read()
                multipart_user_data.add_part(
                    ec2.MultipartBody.from_raw_body(
                        content_type='text/x-shellscript; charset="us-ascii"',
                        body=user_data_xray_txt,
                    )
                )
            if lustre_fs:
                # BUG issue with GPU AMI https://github.com/aws/amazon-ecs-ami/pull/191
                if proc_name in ["xilinx", "nvidia"]:
                    with open(
                        from_root("infrastructure", "constructs", "user_data_gpu.txt")
                    ) as f:
                        user_data_gpu_txt = f.read()
                        multipart_user_data.add_part(
                            ec2.MultipartBody.from_raw_body(
                                content_type='text/x-shellscript; charset="us-ascii"',
                                body=user_data_gpu_txt,
                            )
                        )
                with open(
                    from_root("infrastructure", "constructs", "user_data_lustre.txt")
                ) as f:
                    user_data_lustre_txt = f.read()
                    user_data_lustre_txt = user_data_lustre_txt.replace(
                        "%DNS_NAME%", lustre_fs.dns_name
                    )
                    user_data_lustre_txt = user_data_lustre_txt.replace(
                        "%MOUNT_NAME%", lustre_fs.mount_name
                    )
                    user_data_lustre_txt = user_data_lustre_txt.replace(
                        "%MOUNT_POINT%", "/fsx-lustre"
                    )

                    multipart_user_data.add_part(
                        ec2.MultipartBody.from_raw_body(
                            content_type='text/x-shellscript; charset="us-ascii"',
                            body=user_data_lustre_txt,
                        )
                    )

            # Launch Template
            md5_hash = hashlib.md5(
                multipart_user_data.render().encode(), usedforsecurity=False
            )
            short_hash = md5_hash.hexdigest()[:5]

            launch_template = ec2.LaunchTemplate(
                self,
                "lt-" + proc_name + "-" + short_hash,
                launch_template_name="batch-ffmpeg-lt-" + proc_name + "-" + short_hash,
                user_data=multipart_user_data,
            )
            return launch_template

    def create_compute_environment(self, vpc, security_group, instance_role, lustre_fs):
        if self.processor_config["container_type"] == "FARGATE":
            self.compute_environment = batch.FargateComputeEnvironment(
                self,
                f"batch-fargate-compute-environment-{self.processor_name}",
                compute_environment_name=f"batch-ffmpeg-{self.processor_name}",
                vpc=vpc,
                security_groups=[security_group],
                vpc_subnets=ec2.SubnetSelection(
                    subnet_type=ec2.SubnetType.PRIVATE_ISOLATED
                ),
                spot=self.processor_config.get("spot", False),
            )
        else:
            current_region = self.env.region

            # Check if the current region is in the excluded regions
            excluded_regions = self.processor_config.get("excluded_regions", [])
            is_region_excluded = current_region in excluded_regions
            # Determine the instance types to use
            instance_types = self.processor_config.get("instance_types", None)
            instance_classes = self.processor_config.get("instance_classes", [])
            additional_instances = self.processor_config.get("additional_instances", [])
            if not is_region_excluded:
                instance_classes.extend(additional_instances)

            is_fargate = self.processor_config["container_type"] == "FARGATE"
            launch_template = self.create_launch_template(
                is_fargate, self.processor_name, lustre_fs
            )

            # logger.info(f"Instance classes for {self.processor_name}: {instance_classes}")
            # logger.info(f"Instance types for {self.processor_name}: {instance_types}")
            self.compute_environment = batch.ManagedEc2EcsComputeEnvironment(
                self,
                f"batch-ec2-compute-environment-{self.processor_name}",
                vpc=vpc,
                compute_environment_name=f"batch-ffmpeg-ec2-{self.processor_name}",
                instance_classes=instance_classes,
                instance_types=instance_types,
                instance_role=instance_role,
                use_optimal_instance_classes=False,
                update_to_latest_image_version=True,
                terminate_on_update=False,
                launch_template=launch_template,
                security_groups=[security_group],
                vpc_subnets=ec2.SubnetSelection(
                    subnet_type=ec2.SubnetType.PRIVATE_ISOLATED
                ),
                spot=self.processor_config.get("spot", False),
                maxv_cpus=4096,
            )

    def create_job_queue(self):
        """Create the job queue for the Batch job.

        This method sets up the job queue and associates it with the
        previously created compute environment.
        """
        self.job_queue = batch.JobQueue(
            self,
            "JobQueue",
            job_queue_name=self.job_queue_name,
            priority=1,
            compute_environments=[
                batch.OrderedComputeEnvironment(
                    compute_environment=self.compute_environment, order=1
                )
            ],
        )

        self.job_queue = self.job_queue
        self.job_definition = self.job_definition
