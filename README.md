
# Create a managed FFMPEG workflow for your media jobs using AWS Batch

FFMPEG is an industry standard, open source, widely used utility for handling video. FFMPEG has many capabilities, including encoding and decoding all video compression formats, encoding and decoding audio, encapsulating, and extracting audio, and video from transport streams, and many more. 

If AWS customers wants to use FFMPEG on AWS, they have to maintain FFMPEG by themselves through an EC2 instance and develop a workflow manager to ingest and manipulate media assets. It's painful.
This solution integrates FFMPEG in AWS Services to build a managed FFMPEG by AWS. This solution deploys the FFMPEG command packaged in a container and managed by AWS Batch. When finished, you will execute a FFMPEG command as a job through a REST API. 

With this solution you will have a better usability and control. This solution offers relief from learning curves and maintenance costs for open-source applications.

We identified two use cases:
1. Use a managed FFMPEG solution as a toolbox to manipulate video assets
2. Use a managed FFMPEG solution to benchmark a ffmpeg command through different EC2 families to choose the most efficient and sustainable Amazon EC2 instance to perform the command in a specific workflows.

AWS Batch enables developers, scientists, and engineers to easily and efficiently run hundreds of thousands of batch computing jobs on AWS. AWS Batch dynamically provisions the optimal quantity and type of compute resources (e.g., CPU or memory optimized instances) based on the volume and specific resource requirements of the batch jobs submitted. With AWS Batch, there is no need to install and manage batch computing software or server clusters that you use to run your jobs, allowing you to focus on analyzing results and solving problems. AWS Batch plans, schedules, and executes your batch computing workloads across the full range of AWS compute services and features, such as Amazon EC2 and Spot Instances.

In January 2023, AWS proposes 15 general usage instance families, 11 optimised compute instance families et 14 accelerated computes. By correlating each instance family specification with FFMPEG hardware acceleration API, we understand it is possible to optimize the performance of FFMPEG: 
- **NVIDIA** GPU-powered Amazon EC2 instances : P3 instance family comes equipped with the NVIDIA Tesla V100 GPU. G4dn instance family is powered by NVIDIA T4 GPUs and Intel Cascade Lake CPUs. These GPUs are well suited for video coding workloads and offers enhanced hardware-based encoding/decoding (NVENC/NVDEC).
- **Xilinx** media accelerator cards : VT1 instances are powered by up to 8 Xilinx® Alveo™ U30 media accelerator cards and support up to 96 vCPUs, 192GB of memory, 25 Gbps of enhanced networking, and 19 Gbps of EBS bandwidth. The [Xilinx Video SDK includes an enhanced version of FFmpeg](https://xilinx.github.io/video-sdk/v1.5/using_ffmpeg.html) that can communicate with the hardware accelerated transcode pipeline in Xilinx devices. As [described in this benchmark](https://aws.amazon.com/fr/blogs/opensource/run-open-source-ffmpeg-at-lower-cost-and-better-performance-on-a-vt1-instance-for-vod-encoding-workloads/), VT1 instances can encode VOD assets up to 52% faster, and achieve up to 75% reduction in cost when compared to C5 and C6i instances.
- EC2 instances powered by **Intel** : M6i/C6i instances are powered by 3rd generation Intel Xeon Scalable processors (code named Ice Lake) with an all-core turbo frequency of 3.5 GHz.
- AWS **Graviton**-bases instances : Encoding video on C7g instances, the last [AWS Graviton processor family](https://aws.amazon.com/ec2/graviton/), costs measured 29% less for H.264 and 18% less for H.265 compared to C6i, as described in this blog post ['Optimized Video Encoding with FFmpeg on AWS Graviton Processors'](https://aws.amazon.com/blogs/opensource/optimized-video-encoding-with-ffmpeg-on-aws-graviton-processors/)
- **AMD**-powered EC2 instances: M6a instances are powered by 3rd generation AMD EPYC processors (code named Milan).
- Serverless compute with **Fargate**:  Fargate allows to have a completely serverless architecture for your batch jobs. With Fargate, every job receives the exact amount of CPU and memory that it requests.


To help AWS Customers, we are going to create a managed file-based encoding pipeline using [AWS Batch](https://aws.amazon.com/batch) with FFMPEG in container images. As a starting point, this pipeline uses Intel (C5), Graviton(C6g) Nvidia (G4dn), AMD (C5a, M5a) and Fargate instance families.  

## Disclaimer And Data Privacy Notice
When you deploy this solution, scripts will download different packages with different licenses from various sources. These sources are not controlled by the developer of this script. Additionally, this script can create a non-free and un-redistributable binary. By deploying and using this solution, you are fully aware of this.

## Architecture

The architecture includes 5 main components :

1. **Containers images** are stored in a Amazon ECR (Elastic Container Registry) registry. Each container includes FFMPEG library with a Python wrapper. Container images are specialized per CPU architecture : ARM64, x86-64, NVIDIA.
1. **AWS Batch** is configured with a queue and compute environment per CPU architecture. AWS Batch schedules job queues using Spot Instance compute environments only, to optimize cost.
1. Customers submit jobs through AWS SDKs with the 'SubmitJob' operation or use the **Amazon API Gateway REST API** to easily submit a job with any HTTP library.
1. All media assets ingested and produced are stored on a **Amazon S3** bucket.
1. Observability is managed by **Cloudwatch** and **X-Ray**. All XRay traces are exported on Amazon S3 to benchmark which compute architecture is better for a specific FFMPEG command.

![Architecture](doc/aws-batch-ffmpeg.drawio.png)

## Prerequisites

You need the following prerequisites to set up the solution : 

- An [AWS account](https://signin.aws.amazon.com/signin?redirect_uri=https%3A%2F%2Fportal.aws.amazon.com%2Fbilling%2Fsignup%2Fresume&client_id=signup)  with privileges to create  [AWS Identity and Access Management](http://aws.amazon.com/iam)  (IAM) roles and policies. For more information, see  [Overview of access management: Permissions and policies](https://docs.aws.amazon.com/IAM/latest/UserGuide/introduction_access-management.html) .
- Latest version of [AWS Cloud Development Kit (CDK)](https://docs.aws.amazon.com/cdk/v2/guide/getting_started.html) with a [bootstraping](https://docs.aws.amazon.com/cdk/v2/guide/bootstrapping.html) already done.
- Latest version of [Task](https://taskfile.dev/#/installation)
- Latest version of [Docker](https://docs.docker.com/get-docker/)
- Last version of [Python 3](https://www.python.org/downloads/)

## Deploy the solution with AWS CDK

To deploy the solution on your account, complete the following steps:

1. Clone the github repository http://github.com/aws-samples/aws-batch-with-ffmpeg/
1. execute this list of command : 

```bash
task venv
source .venv/bin/activate
task cdk:deploy
task env
task app:docker-amd64
task app:docker-arm64
task app:docker-nvidia
```

CDK will output the new Amazon S3 bucket and the Amazon API Gateway REST endpoint.

## Use the solution

I execute FFMPEG commands with the **AWS SDKs** or AWS CLI. The solution respects the typical syntax of the FFMPEG command described in the [official documentation](https://ffmpeg.org/ffmpeg.html): 
```bash
ffmpeg [global_options] {[input_file_options] -i input_url} ... {[output_file_options] output_url} ...
````
So, parameters of the solution are 
- `global_options`: FFMPEG global options described in the official documentation.
- `input_file_options`: FFMPEG input file options described in the official documentation.
- `ìnput_url`: AWS S3 url synced to the local storage and tranformed to local path by the solution.
- `output_file_options`: FFMPEG output file options described in the official documentation.
- `output_url`: AWS S3 url synced from the local storage to AWS S3 storage.
- `compute`: Instances family used to compute the media asset : `intel`, `arm`, `amd`, `nvidia`, `fargate`
- `name`: metadata of this job for observability.

 In this example we use the Python SDK Boto3 and we want to cut a specific part of a video. First of all, we uploaded a video in the Amazon S3 bucket created by the solution, and complete the parameters below : 

```python
import boto3
import requests
from urllib.parse import urlparse
from aws_requests_auth.boto_utils import BotoAWSRequestsAuth

# Cloudformation output of the Amazon S3 bucket created by the solution : s3://batch-ffmpeg-stack-bucketxxxx/
s3_bucket_url = "<S3_BUCKET>" 
# Amazon S3 key of the media Asset uploaded on S3 bucket, to compute by FFMPEG command : test/myvideo.mp4
s3_key_input = "<MEDIA_ASSET>"
# Amazon S3 key of the result of FFMPEG Command : test/output.mp4
s3_key_output = "<MEDIA_ASSET>" 
# EC2 instance family : `intel`, `arm`, `amd`, `nvidia`, `fargate`
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

I submit the FFMPEG command with the AWS SDK Boto3 (Python) : 

```python
batch = boto3.client("batch")
result = batch.submit_job(
    jobName=job_name,
    jobQueue="batch-ffmpeg-job-queue-" + compute,
    jobDefinition="batch-ffmpeg-job-definition-" + compute,
    parameters=command,
)
```

I can also submit the same FFMPEG command with the REST API through a HTTP POST method. I control access to this Amazon API Gateway API with [IAM permissions](https://docs.aws.amazon.com/apigateway/latest/developerguide/permissions.html) :

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
url= api_endpoint + compute + '/ffmpeg' 
response = requests.post(url=url, json=command, auth=auth, timeout=2)
```

Per default, AWS Batch chooses by itself an EC2 instance type available. If you want to override it, you can add the `nodeOverride` property when you submit a job with the SDK: 

```python
instance_type = 'c5.large'
result = batch.submit_job(
    jobName=job_name,
    jobQueue="batch-ffmpeg-job-queue-" + compute,
    jobDefinition="batch-ffmpeg-job-definition-" + compute,
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

and with the REST API :

```python
command['instance_type'] = instance_type
url= api_endpoint + compute + '/ffmpeg' 
response = requests.post(url=url, json=command, auth=auth, timeout=2)
```

## Extend the solution

You can customize and extend the solution as you want. For example you can customize the FFMPEG docker image adding libraries or upgrading the FFMPEG version, all docker files are located in [`application/docker-images/`](https://github.com/aws-samples/aws-batch-with-ffmpeg/tree/main/application/docker-images/). You can customize the list of EC2 instances used by the solution with new instance types available in an AWS Region, updating the CDK stack located in this CDK file [`cdk/batch_job_ffmpeg_stack.py`](https://github.com/aws-samples/aws-batch-with-ffmpeg/blob/main/cdk/batch_job_ffmpeg_stack.py#L223).

The FFMPEG wrapper is a Python script `/application/ffmpeg_wrapper.py` which syncs the source media assets from Amazon S3, launches the ffmpeg command and syncs the result to Amazon S3.

The CDK stack is described in the directory `/cdk`.

## Quality metrics

AWS Customers also wants to use this solution to benchmark the video encoding performance of Amazon EC2 instance families. We analyze performance and video quality metrics thanks to AWS X-Ray service. We define 3 segments : Amazon S3 download, FFMPEG Execution and Amazon S3 upload.

If we switch the AWS SSM (Systems Manager) Parameter `/batch-ffmpeg/ffqm` to `TRUE`, quality metrics PSNR, SSIM, VMAF are calculated and exported as an AWS X-RAY metadata and as a JSON file in the Amazon S3 bucket with the key prefix `/metrics/ffqm`.

All AWS X-Ray traces are exported to Amazon s3. An Amazon Glue Crawler provides an Amazon Athena table which we can execute SQL requests.

## Cost

With AWS Batch, you pay as you go based on the time of computing. We use Spot instances to optimize the cost. You can benchmark all instances to find the best one for your use case.

## Clean up

To avoid incurring unnecessary charges, clean up the resources you created for testing this connector.

1. Delete all objects of the Amazon S3 bucket.
2. Inside the Git repository, execute this command in a terminal : `task cdk:destroy`


