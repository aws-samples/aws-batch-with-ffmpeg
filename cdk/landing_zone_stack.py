# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0

from aws_cdk import Stack
from aws_cdk import aws_ec2 as ec2
from aws_cdk import aws_iam as iam
from aws_cdk import aws_logs as logs
from constructs import Construct


class LandingZoneStack(Stack):
    vpc = None

    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)
        # VPC
        self.vpc = ec2.Vpc(
            self,
            id="vpc",
            nat_gateways=0,
            max_azs=99,
            subnet_configuration=[
                ec2.SubnetConfiguration(
                    name="private-isolated-subnet",
                    subnet_type=ec2.SubnetType.PRIVATE_ISOLATED,
                )
            ],
        )
        subnet_selection = ec2.SubnetSelection(
            subnet_type=ec2.SubnetType.PRIVATE_ISOLATED
        )

        # VPC Flow Logs
        log_group = logs.LogGroup(self, "flow-logs-group")
        flow_log_role = iam.Role(
            self,
            "MyCustomRole",
            assumed_by=iam.ServicePrincipal("vpc-flow-logs.amazonaws.com"),
        )
        ec2.FlowLog(
            self,
            "FlowLog",
            resource_type=ec2.FlowLogResourceType.from_vpc(self.vpc),
            destination=ec2.FlowLogDestination.to_cloud_watch_logs(
                log_group, flow_log_role
            ),
        )

        # VPC Endpoints
        self.vpc.add_gateway_endpoint(
            "vpce-s3",
            service=ec2.GatewayVpcEndpointAwsService.S3,
            subnets=[subnet_selection],
        )
        self.vpc.add_interface_endpoint(
            "vpce-ecr",
            service=ec2.InterfaceVpcEndpointAwsService.ECR,
            subnets=subnet_selection,
        )
        self.vpc.add_interface_endpoint(
            "vpce-ecr-docker",
            service=ec2.InterfaceVpcEndpointAwsService.ECR_DOCKER,
            subnets=subnet_selection,
        )
        self.vpc.add_interface_endpoint(
            "vpce-cloudwatch-logs",
            service=ec2.InterfaceVpcEndpointAwsService.CLOUDWATCH_LOGS,
            subnets=subnet_selection,
        )
        self.vpc.add_interface_endpoint(
            "vpce-cloudwatch",
            service=ec2.InterfaceVpcEndpointAwsService.CLOUDWATCH,
            subnets=subnet_selection,
        )
        self.vpc.add_interface_endpoint(
            "vpce-ecs",
            service=ec2.InterfaceVpcEndpointAwsService.ECS,
            subnets=subnet_selection,
        )
        self.vpc.add_interface_endpoint(
            "vpce-ecs-agent",
            service=ec2.InterfaceVpcEndpointAwsService.ECS_AGENT,
            subnets=subnet_selection,
        )
        self.vpc.add_interface_endpoint(
            "vpce-ecs-telemetry",
            service=ec2.InterfaceVpcEndpointAwsService.ECS_TELEMETRY,
            subnets=subnet_selection,
        )
        self.vpc.add_interface_endpoint(
            "vpce-xray",
            service=ec2.InterfaceVpcEndpointAwsService.XRAY,
            subnets=subnet_selection,
        )
        self.vpc.add_interface_endpoint(
            "vpce-ssm",
            service=ec2.InterfaceVpcEndpointAwsService.SSM,
            subnets=subnet_selection,
        )
        self.vpc.add_interface_endpoint(
            "vpce-ssm-messages",
            service=ec2.InterfaceVpcEndpointAwsService.SSM_MESSAGES,
            subnets=subnet_selection,
        )
        self.vpc.add_interface_endpoint(
            "vpce-ec2-messages",
            service=ec2.InterfaceVpcEndpointAwsService.EC2_MESSAGES,
            subnets=subnet_selection,
        )
        self.vpc.add_interface_endpoint(
            "vpce-ec2",
            service=ec2.InterfaceVpcEndpointAwsService.EC2,
            subnets=subnet_selection,
        )
