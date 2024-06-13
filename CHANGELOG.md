# Changelog

All notable changes to this project will be documented in this file.

## version v0.0.8

### Added

- New compute family available Fargate with Graviton 2: You can run your applications using the Fargate (Serverless) launch type with the ARM64 architecture.
- Upgrade : FFmpeg 7.0.1 for `intel`, `arm`, `amd`, `nvidia`, `fargate`, `fargate-arm`
- Improve compatibility with several AWS Regions: ap-southeast-2``ap-south-1``sa-east-1``eu-west-3``us-east-1``us-west-2``eu-central-1`

### Changed

- Fix stack destroy issues
- Fix multi region deployment

## version v0.0.7

### Changed

- Deploy Interface VPC Endpoint in one AZ to optimize cost [(#17)](https://github.com/aws-samples/aws-batch-with-ffmpeg/issues/17)
- Fix pyyaml dependency

## version v0.0.6

### Added

- Add Amazon Step Function workflow to massively parallelize jobs
- Add Amazon FSx for Lustre cluster to optimize the upload/download of large media assets
- Add Amazon System Manager Automation to preload large media assets from Amazon S3 to FSx for Lustre cluster
- Add API resources for Step Functions
- Document HTTP REST API

### Changed

- Refactor all cdk stacks
- **Breaking:** Refactor HTTP REST API
- Upgrade Nvidia Container to CUVID 12.3.1

## version v0.0.5

- Upgrade FFmpeg to 6.0 (snapshots)
- Upgrade all FFmpeg libraries including decoders and encoders

## version v0.0.4

- Optimize code linting
- Fix security issues
- Refactor list of AWS EC2 Instance families per Region without boto3 (doc/architecture/0003-rollback-automatic-list-of-instance-types-per-aws-region.md)
- Upgrade AWS CDK libraries including AWS Batch to 2.96 and CDK Nag
- Add new compute instance family: VT1 with the support of AMD-Xilinx Video SDK 3.0 (<https://aws.amazon.com/about-aws/whats-new/2023/08/amazon-ec2-vt1-improved-control-stream-quality-latency-bandwidth/>)
- Upgrade Python Lambda Runtime and add runtime management to AUTO
- Upgrade Python Container Runtime

## version v0.0.3

- Update FFMPEG 5.1
- Update Nvidia Cuda
- Fix issue on AWS Athena View

## version v0.0.2

- Add FFmpeg Quality Metrics to AWS Glue Crawler
- Create AWS Athena Views for PSNR, SSIM, VMAF quality metrics
- Optimize code linting
- Dynamically look after AWS EC2 Instance types per AWS Region
- Add AWS Service Catalog Registry
- Document architecture decisions
