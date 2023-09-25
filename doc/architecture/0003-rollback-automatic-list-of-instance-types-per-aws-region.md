# 3. Rollback automatic list of instance types per AWS Region

Date: 2023-08-26

## Status

Accepted

## Context

List of AWS EC2 instance types / families are different per AWS Region. This list depends of the deployment of EC2 instances in each AWS Region.
The first iteration to find the list of AWS EC2 instance types per AWS Region, was to develop a Boto3 function.

## Decision

I don't like to use Boto3 code in AWS CDK because the deployment process needs to have specific IAM policies for this Boto3 function in addition to Cloudformation.
Following the "Least Priviledge" rule, I have found another solution with the last version of AWS CDK Batch Alpha where I can simply list all AWS EC2 Instance families per AWS Regions.

## Consequences

I have to maintain a list of exceptions per AWS Regions for AWS EC2 instance families.
