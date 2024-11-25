from aws_cdk import Stack, Tags
from aws_cdk import aws_ec2 as ec2
from aws_cdk import aws_iam as iam
from aws_cdk import aws_logs as logs
from constructs import Construct
from typing import List


class LandingZoneStack(Stack):
    """A stack that sets up the foundational network infrastructure.

    This stack creates a VPC with isolated subnets, VPC endpoints, and
    VPC flow logs. It's designed to be the base network layer for other
    stacks in the application.
    """

    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        self.vpc = self.create_vpc()
        self.create_vpc_endpoints()
        self.create_vpc_flow_logs()

        # Tag all resources in this stack
        Tags.of(self).add("Stack", "LandingZone")

    def create_vpc(self) -> ec2.Vpc:
        """Create and return a VPC with isolated subnets."""
        return ec2.Vpc(
            self,
            "VPC",
            max_azs=99,
            nat_gateways=0,
            subnet_configuration=[
                ec2.SubnetConfiguration(
                    name="PrivateIsolated",
                    subnet_type=ec2.SubnetType.PRIVATE_ISOLATED,
                    cidr_mask=24,
                )
            ],
            enable_dns_hostnames=True,
            enable_dns_support=True,
        )

    def create_vpc_endpoints(self) -> None:
        """Create VPC endpoints for various AWS services."""
        # Define the services that need interface endpoints
        interface_services = [
            "ecr.api",
            "ecr.dkr",
            "logs",
            "monitoring",
            "ecs",
            "ecs-agent",
            "ecs-telemetry",
            "xray",
            "ssm",
            "ssmmessages",
            "ec2messages",
        ]

        # Create interface endpoints
        for service in interface_services:
            self.vpc.add_interface_endpoint(
                f"VPCEndpoint{service.replace('.', '').replace('-', '').capitalize()}",
                service=ec2.InterfaceVpcEndpointAwsService(service),
            )

        # Create gateway endpoints
        self.vpc.add_gateway_endpoint(
            "S3Endpoint",
            service=ec2.GatewayVpcEndpointAwsService.S3,
            subnets=[ec2.SubnetSelection(subnet_type=ec2.SubnetType.PRIVATE_ISOLATED)],
        )

    def create_vpc_flow_logs(self) -> None:
        """Set up VPC flow logs."""
        log_group = logs.LogGroup(self, "VPCFlowLogsGroup")

        flow_log_role = iam.Role(
            self,
            "VPCFlowLogsRole",
            assumed_by=iam.ServicePrincipal("vpc-flow-logs.amazonaws.com"),
        )

        ec2.FlowLog(
            self,
            "VPCFlowLog",
            resource_type=ec2.FlowLogResourceType.from_vpc(self.vpc),
            destination=ec2.FlowLogDestination.to_cloud_watch_logs(
                log_group, flow_log_role
            ),
        )

    @property
    def isolated_subnets(self) -> List[ec2.ISubnet]:
        """Return the list of isolated subnets in the VPC."""
        return self.vpc.select_subnets(
            subnet_type=ec2.SubnetType.PRIVATE_ISOLATED
        ).subnets
