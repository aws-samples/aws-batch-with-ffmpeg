# 2. Implement automatic list of instance types per AWS Region

Date: 2023-05-17

## Status

Accepted

## Context

Lists of instance types per CPU architecture (Intel, Graviton, Nvidia, ...) are static in a CDK Stack Code.
So the solution can not fully leverage AWS Spot instances in a Region.

## Decision

Objective: Create a dynamic list of instance types per AWS Region

Two options:

1. Create AWS Cloudformation custom resource with the AWS CDK custom resource provider "framework". Issue : Impossible to AWS CDK L2 Construct for AWS Batch.
2. Use boto3 in the CDK code, the list is generated during AWS CDK synth command

In order to keep it simple and stupid (KISS), I choose the second option.
