# 1. Implement Athena Views

Date: 2023-05-11

## Context

Initially, Athena views are created by AWS CDK at the same time of AWS Glue Crawler.

After AWS Glue Crawler run, each Athena views were stale

## Decision

Athena views provisioned in AWS CDK is deleted.
Athena views are created / updated after each run of AWS Glue Crawler.
Creation of Athena views is now inside the AWS Lambda "metrics" which is executed by a AWS Cloudwatch Event Schedule Rule every 2 hours.
