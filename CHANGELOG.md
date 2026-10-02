# Changelog

All notable changes to this project will be documented in this file.

## version v1.1.1

### Security

- The three free-form ffmpeg option fields (`global_options`, `input_file_options`, `output_file_options`) are validated in the wrapper before the command is built: a token carrying a network or indirection protocol prefix (`http`, `tcp`, `concat`, `subfile`, ...) or a resource-reaching flag (`-i`, `-protocol_whitelist`, `-dump_attachment`, `-attach`) is rejected. The wrapper is the point the API caller cannot bypass.
- ffmpeg runs with `-protocol_whitelist file,crypto,data,pipe` before every input, so an input is bound to local protocols only. Together with the option validation this closes the SSRF and local-file-read paths through the submitted options.
- The Batch compute hosts enforce IMDSv2 (`HttpTokens: required`) on the launch template, so a request forged from inside a container cannot reach the instance metadata credential path over IMDSv1.
- The worker security group no longer allows all outbound traffic: egress is scoped to HTTPS (443) and the Amazon S3 Files NFS port (2049). The subnets are isolated with no NAT or internet gateway, so HTTPS reaches only the VPC endpoints, never the internet.
- The REST API carries a resource policy restricting `execute-api:Invoke` to principals of the account that owns the API, in defense in depth on top of the IAM authorizer on every method.

## version v1.1.0

### Added

- Amazon S3 Files shared file system, replacing FSx for Lustre: the media assets of the data bucket are exposed as an NFS file system on `/mnt/s3files`, so jobs read and write them in place instead of copying them to local storage. Enable it with `batch-ffmpeg:shared-fs:enable` in `cdk.json`. See [ADR 6](doc/architecture/0006-replace-fsx-lustre-with-amazon-s3-files.md).
- Enabling that file system needs no manual preparation: whenever the solution writes an object through the S3 API, it materializes the directories of that prefix with the POSIX ownership metadata S3 Files reads, stamped with the identity the container runs as.
- An integration test that measures how long the bucket takes to expose the output of a job written through the file system, so the window is a measurement instead of a claim.
- Unit tests of the architecture diagrams: a diagram edited without re-exporting, an edge pointing at a deleted shape, a missing image or a stale component count now fail the build.
- Security scanning with the AWS Labs Automated Security Helper, `task security:ash`, configured in `.ash/.ash.yaml`.

### Changed

- Containers run as the non root `ffmpeg` user, IAM policies are narrowed to least privilege, and the Systems Manager inputs are validated.
- The architecture diagrams describe the deployed architecture again: Amazon S3 Files, and the two states the Step Functions state machine actually declares.
- The HTTP API documentation is regenerated from the deployed API.
- Container builds take FFmpeg from the GitHub mirror and freetype from the Savannah mirror, and clone nv-codec-headers over HTTP/1.1, which removes the build failures those sources caused.
- The CI runner image moves to Ubuntu Noble with the current CDK, and deploys are serialized so two pipelines no longer update the same stack at once.
- The stacks are decoupled: the API stack no longer imports the job definition export of the Batch stack, and the Batch stack resolves the shared file system through SSM parameters instead of CloudFormation exports, which is what blocked replacing it.
- The pre-commit chain runs and passes: `detect-aws-credentials` no longer requires static credentials, `detect-private-key` is added, and bandit moves to a release that does not import `pbr` at runtime.
- bandit no longer skips B608 across the whole repository; the three queries that raise it carry the reason on the line itself.

### Removed

- Xilinx VT1 support, the instances no longer existing: the `xilinx` compute value, its container image, its CI jobs and its documentation are gone.
- FSx for Lustre, its scratch cluster and the Systems Manager Automation that preloaded it.
- The commented FSx release and Systems Manager preload endpoints of the API stack, and four unreferenced screenshots of the state machine.

## version v1.0.0

### Changed

- CDK and application code refactored
    1. Modular architecture with clear separation of concerns
    2. Reusable components and shared utilities
    3. Flexible configuration management

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
