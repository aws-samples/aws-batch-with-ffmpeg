# Create a managed FFmpeg workflow for your media jobs using AWS Batch

_Blog post : <https://aws.amazon.com/blogs/opensource/create-a-managed-ffmpeg-workflow-for-your-media-jobs-using-aws-batch/>_

<!--TOC-->

- [Create a managed FFmpeg workflow for your media jobs using AWS Batch](#create-a-managed-ffmpeg-workflow-for-your-media-jobs-using-aws-batch)
  - [Introduction](#introduction)
  - [Disclaimer And Data Privacy Notice](#disclaimer-and-data-privacy-notice)
  - [Architecture](#architecture)
    - [Architecture Decision Records](#architecture-decision-records)
    - [Diagram](#diagram)
  - [Install](#install)
    - [Prerequisites](#prerequisites)
  - [Deploy the solution with AWS CDK](#deploy-the-solution-with-aws-cdk)
  - [Use the solution](#use-the-solution)
    - [Use the solution at scale with AWS Step Functions](#use-the-solution-at-scale-with-aws-step-functions)
    - [Use the solution with Amazon FSx for Lustre cluster](#use-the-solution-with-amazon-fsx-for-lustre-cluster)
    - [Extend the solution](#extend-the-solution)
  - [Performance and quality metrics](#performance-and-quality-metrics)
  - [Cost](#cost)
  - [Clean up](#clean-up)

<!--TOC-->

## Introduction

[FFmpeg](https://ffmpeg.org/) is an open source, industry standard utility for handling video. To use FFmpeg on AWS, customers must maintain FFmpeg themselves on EC2 and build workflow managers to ingest and process media. This solution integrates FFmpeg with AWS services to create a managed offering. It packages FFmpeg commands in containers, managed by [AWS Batch](https://aws.amazon.com/batch/). Customers can then execute FFmpeg jobs through a REST API.

AWS Batch is a fully managed service that enables developers to run hundreds of thousands of batch computing jobs on AWS. It automatically provisions the optimal quantity and type of compute resources, without the need for you to install and manage batch computing software or server clusters.

This solution improves usability and control. It relieves the burden of maintaining open source software and building custom workflow managers. Customers benefit from reduced costs and learning curves.

AWS proposes several general usage instance families, optimised compute instance families and 14 accelerated computes. By correlating each instance family specification with FFmpeg hardware acceleration API, we understand it is possible to optimize the performance of FFmpeg:

- **NVIDIA with Intel** GPU-powered Amazon EC2 instances: G4dn instance family is powered by NVIDIA T4 GPUs and Intel Cascade Lake CPUs. G5 instance family is powered by NVIDIA A10G Tensor Core GPU. These GPUs are well suited for video encoding workloads and offer enhanced hardware-based encoding/decoding (NVENC/NVDEC). This blog post ['Optimizing video encoding with FFmpeg using NVIDIA GPU-based Amazon EC2 instances'](https://aws.amazon.com/blogs/compute/optimizing-video-encoding-with-ffmpeg-using-nvidia-gpu-based-amazon-ec2-instances/) compares video encoding performance between CPUs and Nvidia GPUs and to determine the price/performance ratio in different scenarios.
- **Xilinx with Intel** media accelerator cards: VT1 instances are powered by up to 8 Xilinx® Alveo™ U30 media accelerator cards and support up to 96 vCPUs, 192GB of memory, 25 Gbps of enhanced networking, and 19 Gbps of EBS bandwidth. The [Xilinx Video SDK includes an enhanced version of FFmpeg](https://xilinx.github.io/video-sdk/v1.5/using_FFmpeg.html) that can communicate with the hardware accelerated transcode pipeline in Xilinx devices. As [described in this benchmark](https://aws.amazon.com/fr/blogs/opensource/run-open-source-ffmpeg-at-lower-cost-and-better-performance-on-a-vt1-instance-for-vod-encoding-workloads/), VT1 instances can encode VOD assets up to 52% faster, and achieve up to 75% reduction in cost when compared to C5 and C6i instances.
- EC2 instances powered by **Intel**: M6i/C6i instances are powered by 3rd generation Intel Xeon Scalable processors (code named Ice Lake) with an all-core turbo frequency of 3.5 GHz.
- EC2 instances powered by **AWS Graviton**: Encoding video on C7g instances, the last [AWS Graviton processor family](https://aws.amazon.com/ec2/graviton/), costs measured 29% less for H.264 and 18% less for H.265 compared to C6i, as described in this blog post ['Optimized Video Encoding with FFmpeg on AWS Graviton Processors'](https://aws.amazon.com/fr/blogs/opensource/optimized-video-encoding-with-ffmpeg-on-aws-graviton-processors/)
- EC2 instances powered by **AMD**: M6a instances are powered by 3rd generation AMD EPYC processors (code named Milan).
- Serverless compute with **Fargate**: Fargate allows to have a completely serverless architecture for your batch jobs. With Fargate, every job receives the exact amount of CPU and memory that it requests.

We are going to create a managed file-based encoding pipeline with [AWS Batch](https://aws.amazon.com/batch) and FFmpeg in containers.

## Disclaimer And Data Privacy Notice

When you deploy this solution, scripts will download different packages with different licenses from various sources. These sources are not controlled by the developer of this script. Additionally, this script can create a non-free and un-redistributable binary. By deploying and using this solution, you are fully aware of this.

## Architecture

The architecture includes 5 main components :

1. Containers images are stored in a Amazon ECR (Elastic Container Registry) registry. Each container includes FFmpeg library with a Python wrapper. Container images are specialized per CPU architecture : ARM64, x86-64, NVIDIA, and Xilinx.
1. AWS Batch is configured with a queue and compute environment per CPU architecture. AWS Batch schedules job queues using Spot Instance compute environments only, to optimize cost.
1. Customers submit jobs through AWS SDKs with the `SubmitJob` operation or use the Amazon API Gateway REST API to easily submit a job with any HTTP library.
1. All media assets ingested and produced are stored on an Amazon S3 bucket.
1. [Amazon FSx for Lustre](https://aws.amazon.com/fr/fsx/lustre/) seamlessly integrates with Amazon S3, enabling transparent access to S3 objects as files. Amazon FSx for Lustre is ideally suited for temporary storage and short-term data processing due to its configuration as a Scratch file system. This eliminates the need to move large media assets to local storage.
1. Observability is managed by Amazon Cloudwatch and AWS X-Ray. All XRay traces are exported on Amazon S3 to benchmark which compute architecture is better for a specific FFmpeg command.
1. [Amazon Step Functions](https://aws.amazon.com/step-functions/)  reliably processes huge volumes of media assets with FFmpeg on AWS Batch. it handles job failures, and AWS service limits.

### Architecture Decision Records

1. [Implement Athena Views](doc/architecture/0001-implement-athena-views.md)
1. [Implement automatic list of instance types per AWS Region](doc/architecture/0002-implement-automatic-list-of-instance-types-per-aws-region.md)
1. [Rollback automatic list of instance types per AWS Region](doc/architecture/0003-rollback-automatic-list-of-instance-types-per-aws-region.md)
1. [Implement Step Functions Dynamic Map](doc/architecture/0004-implement-step-functions-dynamic-map.md)
1. [Implement FSx Lustre Scratch cluster](doc/architecture/0005-implement-fsx-lustre-scratch-cluster.md)

### Diagram

![Architecture](doc/aws-batch-ffmpeg.drawio.png)

## Install

### Prerequisites

You need the following prerequisites to set up the solution :

- An AWS account
- Latest version of [AWS Cloud Development Kit (CDK)](https://docs.aws.amazon.com/cdk/v2/guide/getting_started.html) with a [bootstraping](https://docs.aws.amazon.com/cdk/v2/guide/bootstrapping.html) already done.
- Latest version of [Task](https://taskfile.dev/#/installation)
- Latest version of [Docker](https://docs.docker.com/get-docker/)
- Last version of [Python 3](https://www.python.org/downloads/)

## Deploy the solution with AWS CDK

To deploy the solution on your account, complete the following steps:

1. Clone the github repository <http://github.com/aws-samples/aws-batch-with-FFmpeg/>
1. execute this list of command :

```bash
task venv
source .venv/bin/activate
task cdk:deploy
task env
task app:docker-amd64
task app:docker-arm64
task app:docker-nvidia
task:app:docker-xilinx
```

CDK will output the new Amazon S3 bucket and the Amazon API Gateway REST endpoint.

## Use the solution

I can execute FFmpeg commands with the **AWS SDKs**, AWS CLI or HTTP REST API. The solution respects the typical syntax of the FFmpeg command described in the [official documentation](https://FFmpeg.org/FFmpeg.html):

```bash
ffmpeg [global_options] {[input_file_options] -i input_url} ... {[output_file_options] output_url} ...
```

So, parameters of the solution are

- `global_options`: FFmpeg global options described in the official documentation.
- `input_file_options`: FFmpeg input file options described in the official documentation.
- `ìnput_url`: AWS S3 url synced to the local storage and tranformed to local path by the solution.
- `output_file_options`: FFmpeg output file options described in the official documentation.
- `output_url`: AWS S3 url synced from the local storage to AWS S3 storage.
- `compute`: Instances family used to compute the media asset : `intel`, `arm`, `amd`, `nvidia`, `fargate`, `xilinx`
- `name`: metadata of this job for observability.

The solution has different FFmpeg versions per AWS EC2 instance families.

| **Compute** | **FFmpeg version per default** | **FFmpeg version(s) available** |
|-------------|--------------------------------|---------------------------------|
| intel       | 6.0 (snapshot)                 | 6.0, 5.1                        |
| arm         | 6.0 (snapshot)                 | 6.0, 5.1                        |
| amd         | 6.0 (snapshot)                 | 6.0, 5.1                        |
| nvidia      | 6.0 (snapshot)                 | 6.0, 5.1                        |
| fargate     | 6.0 (snapshot)                 | 6.0, 5.1                        |
| xilinx      | 4.4                            | 4.4                             |

In this example we use the AWS SDK "Boto3" (Python) and I want to cut a specific part of a video. First of all, I uploaded a video in the Amazon S3 bucket created by the solution, and complete the parameters below :

```python
import boto3
import requests
from urllib.parse import urlparse
from aws_requests_auth.boto_utils import BotoAWSRequestsAuth

# Cloudformation output of the Amazon S3 bucket created by the solution : s3://batch-FFmpeg-stack-bucketxxxx/
s3_bucket_url = "<S3_BUCKET>"
# Amazon S3 key of the media Asset uploaded on S3 bucket, to compute by FFmpeg command : test/myvideo.mp4
s3_key_input = "<MEDIA_ASSET>"
# Amazon S3 key of the result of FFmpeg Command : test/output.mp4
s3_key_output = "<MEDIA_ASSET>"
# EC2 instance family : `intel`, `arm`, `amd`, `nvidia`, `fargate`, `xilinx`
compute = "intel"
job_name = "clip-video"

command={
    "name": job_name,
    #"global_options":  "",
    "input_url" : s3_bucket_url + s3_key_input,
    #"input_file_options" : "",
    "output_url" : s3_bucket_url + s3_key_output,
    "output_file_options": "-ss 00:00:10 -t 00:00:15 -c:v copy -c:a copy"
}
```

I submit the FFmpeg command with the AWS SDK Boto3 (Python) :

```python
batch = boto3.client("batch")
result = batch.submit_job(
    jobName=job_name,
    jobQueue="batch-ffmpeg-job-queue-" + compute,
    jobDefinition="batch-ffmpeg-job-definition-" + compute,
    parameters=command,
)
```

I can also submit the same FFmpeg command with the REST API through a HTTP POST method ([API Documentation](doc/api.md)). I control access to this Amazon API Gateway REST API with [IAM permissions](https://docs.aws.amazon.com/apigateway/latest/developerguide/permissions.html) :

```python
# AWS Signature Version 4 Signing process with Python Requests
def apig_iam_auth(rest_api_url):
    domain = urlparse(rest_api_url).netloc
    auth = BotoAWSRequestsAuth(
        aws_host=domain, aws_region="<AWS_REGION>", aws_service="execute-api"
    )
    return auth
# Cloudformation output of the Amazon API Gateway REST API created by the solution : https://xxxx.execute-api.xx-west-1.amazonaws.com/prod/
api_endpoint = "<API_ENDPOINT>"
auth = apig_iam_auth(api_endpoint)
url= api_endpoint + 'batch/execute/' + compute
response = requests.post(url=url, json=command, auth=auth, timeout=2)
```

Per default, AWS Batch chooses by itself an EC2 instance type available. If I want to override it, I can add the `nodeOverride` property when I submit a job with the SDK:

```python
instance_type = 'c5.large'
result = batch.submit_job(
    jobName=job_name,
    jobQueue="batch-FFmpeg-job-queue-" + compute,
    jobDefinition="batch-FFmpeg-job-definition-" + compute,
    parameters=command,
    nodeOverrides={
            "nodePropertyOverrides": [
                {
                    "targetNodes": "0,n",
                    "containerOverrides": {
                        "instanceType": instance_type,
                    },
                },
            ]
        },
    )
```

I can have the status of the AWS Batch job execution with the AWS API [Batch::DescribeJobs](https://docs.aws.amazon.com/batch/latest/APIReference/API_DescribeJobs.html) and with the HTTP REST API ([API Documentation](doc/api.md)):

```python
command['instance_type'] = instance_type
url= api_endpoint + '/batch/describe'
response = requests.post(url=url, json=command, auth=auth, timeout=2)
```

### Use the solution at scale with AWS Step Functions

I can process a full library (100000's) of media assets on AWS S3, thanks to AWS Step Functions. I can execute FFmpeg commands at scale with the AWS SDKs, the AWS Command Line Interface (AWS CLI) and the Amazon API Gateway REST API ([API Documentation](doc/api.md)).

![Step Functions](doc/step_functions.png)

In this example, we use the AWS CLI. A Step Functions execution receives a JSON text as input and passes that input to the first state in the workflow. Here is the JSON input.json designed for the solution:

```json
{
  "name": "pytest-sdk-audio",
  "compute": "intel",
  "input": {
    "s3_bucket": "<s3_bucket>",
    "s3_prefix": "media-assets/",
    "file_options": "null"
  },
  "output": {
    "s3_bucket": "<s3_bucket>",
    "s3_prefix": "output/",
    "s3_suffix": "",
    "file_options": "-ac 1 -ar 48000"
  },
  "global": {
    "options": "null"
  }
}
```

Parameters of this `input.json are:

- `$.name`: metadata of this job for observability.
- `$.compute`: Instances family used to compute the media asset : `intel`, `arm`, `amd`, `nvidia`, `xilinx`.
- `$.input.s3_bucket` and `$.input.s3_prefix`: S3 url of the list of Amazon S3 Objects to be processed by FFMPEG.
- `$.input.file_options`: FFmpeg input file options described in the official documentation.
- `$.output.s3_bucket` and `$.output.s3_prefix`: S3 url where all processed media assets will be stored on Amazon S3.
- `$.output.s3_suffix` : Suffix to add to all processed media assets which will be stored on an Amazon S3 Bucket
- `$.output.file_options`: FFmpeg output file options described in the official documentation.
- `$.global.options`: FFmpeg global options described in the official documentation.

And, I submit this FFmpeg command described in JSON input file with the AWS CLI :

```bash
aws stepfunctions start-execution --state-machine-arn arn:aws:states:<region>:<accountid>:stateMachine:batch-ffmpeg-state-machine --name batch-ffmpeg-execution --input "$(jq -R . input.json --raw-output)"“
```

The Amazon S3 url of the processed media is: `s3://{$.output.s3_bucket}{$.output.s3_suffix}{Input S3 object key}{$.output.s3_suffix}`

### Use the solution with Amazon FSx for Lustre cluster

To efficiently process large media files, avoid spending compute time uploading and downloading media to temporary storage. Instead, use an Amazon FSx for Lustre file system in Scratch mode with Amazon S3 object storage. This provides a cost-effective, durable, and flexible solution.

Before deploying the CDK stack, I enable the deployment of this feature and configure the storage capacity of the cluster in the `/cdk.json` file.

```json
    "batch-ffmpeg:lustre-fs": {
      "enable": true,
      "storage_capacity_gi_b": 1200
    }
```

The FFmpeg wrapper transparently converts S3 URLs to lustre filesystem requests when enabled. The integration requires no code changes.

This feature is not available with `fargate` (<https://github.com/aws/containers-roadmap/issues/650>) and `xilinx` (<https://github.com/Xilinx/video-sdk/issues/85>)

Lustre filesystem file manipulation (preload and release) occurs through the Amazon API Gateway Rest API calls ([API Documentation](doc/api.md)). This enables full integration into media supply chain workflows.

![Media Supply Chain](doc/media_supply_chain.png)

The solution deployed an AWS System Manager Document `batch-ffmpeg-lustre-preload` which preloads a media asset in the Lustre filesystem. This SSM Document is available through the Amazon API Gateway Rest API ([API Documentation](doc/api.md)).

To release files on the FSx for Lustre filesystem, I use the AWS API [Amazon FSx::CreateDataRepositoryTask](https://docs.aws.amazon.com/fsx/latest/APIReference/API_CreateDataRepositoryTask.html) with the type of data repository task `RELEASE_DATA_FROM_FILESYSTEM` or the Amazon API Gateway Rest API ([API Documentation](doc/api.md)).

### Extend the solution

I can customize and extend the solution as I want. For example I can customize the FFmpeg docker image adding libraries or upgrading the FFmpeg version, all docker files are located in [`application/docker-images/`](https://github.com/aws-samples/aws-batch-with-FFmpeg/tree/main/application/docker-images/).

The FFmpeg wrapper is a Python script `/application/FFmpeg_wrapper.py` which syncs the source media assets from the Amazon S3 bucket, launches the FFmpeg command and syncs the result to the Amazon S3 bucket.

The CDK stack is described in the directory `/cdk`.

## Performance and quality metrics

AWS Customers also wants to use this solution to benchmark the video encoding performance and quality of Amazon EC2 instance families. I analyze performance and video quality metrics thanks to AWS X-Ray service. i define 3 segments : Amazon S3 download, FFmpeg Execution and Amazon S3 upload.

If I switch the AWS SSM (Systems Manager) Parameter `/batch-ffmpeg/ffqm` to `TRUE`, quality metrics PSNR, SSIM, VMAF are calculated and exported as an AWS X-RAY metadata and as a JSON file in the Amazon S3 bucket with the key prefix `/metrics/ffqm`. Those metrics are available through AWS Athena views `batch_FFmpeg_ffqm_psnr`, `batch_FFmpeg_ffqm_ssim`, `batch_FFmpeg_ffqm_vmaf`.

All AWS X-Ray traces are exported to Amazon s3. An Amazon Glue Crawler provides an Amazon Athena table `batch_FFmpeg_xray` and Amazon Athena view `batch_FFmpeg_xray_subsegment`.

You could then create dashboards with Amazon Quicksight like this one :

![Quicksight](doc/metrics_analysis.jpg)

## Cost

AWS Batch optimizes compute costs by paying only for used resources. Using Spot instances leverages unused EC2 capacity for significant savings over On-Demand instances. Benchmark different instance types and sizes to find the optimal workload configuration. Test options like GPU versus CPU to balance performance and cost.

## Clean up

To prevent unwanted charges after evaluating this solution, delete created resources by:

1. Delete all objects in the Amazon S3 bucket used for testing. I can remove these objects from the S3 console by selecting all objects and clicking "Delete."
2. Destroy the AWS CDK stack that was deployed for testing. To do this, I open a terminal in the Git repository and run: `task cdk:destroy`
3. Verify that all resources have been removed by checking the AWS console. This ensures no resources are accidentally left running, which would lead to unexpected charges.
