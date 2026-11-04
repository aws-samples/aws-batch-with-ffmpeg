# 7. G5g (Graviton + NVIDIA) GPU is not supported on AWS Batch managed compute

Date: 2026-10-04

## Status

Rejected

Investigated for [GitHub issue 14](https://github.com/aws-samples/aws-batch-with-ffmpeg/issues/14)
(add a G5g compute family). A working G5g GPU processor is not achievable on
AWS Batch managed compute today; the issue stays open as a service limitation.

## Context

G5g is the Graviton (arm64) instance family with an NVIDIA T4g GPU. The ask was
a `g5g` processor with its own compute environment, queue, job definition and
API endpoint, so GPU transcoding could run on arm64.

Two facts shaped the investigation, both checked against the live AWS APIs and
documentation rather than the issue comments, which predate the current state:

1. AWS Batch has no managed image type that selects an arm64 GPU AMI. The only
   AWS-published arm64 + NVIDIA ECS AMI is Bottlerocket
   (`/aws/service/bottlerocket/aws-ecs-2-nvidia/arm64/latest/image_id`), which
   would be supplied as a custom AMI id override.
2. g5g is offered only in some Regions (us-east-1, us-west-2, eu-central-1,
   ap-northeast-1, ap-southeast-1), not in the project's eu-west-1.

## Decision

Do not add a `g5g` processor. The decision is based on a live probe in
us-east-1 (account 545746531391), not on assumption.

### What the probe proved

- A Batch MANAGED EC2 compute environment with `instanceTypes:[g5g]` + the
  Bottlerocket arm64 NVIDIA AMI override + `ECS_AL2023_NVIDIA` is **accepted**
  and reaches `VALID / ENABLED / ComputeEnvironment Healthy`. The compute
  environment wiring is correct; the earlier eu-west-1 failure was only the
  Region not offering g5g.
- A job with a `GPU` resource requirement stays stuck in `RUNNABLE` with
  `MISCONFIGURATION:JOB_RESOURCE_REQUIREMENT`. g5g is not in the Batch/ECS GPU
  instance-family list (`p3, p4, p5, p6, g3, g3s, g4, g5, g6`), so Batch never
  places a GPU job onto it.
- A job **without** the GPU requirement is placed and runs on g5g, but the
  container sees no GPU device: `/dev/nvidia* : No such file or directory`. ECS
  pins GPUs and switches to the NVIDIA runtime only for recognised GPU
  families, which exclude g5g.

### Why there is no workaround

The documented ECS GPU-sharing path (drop the GPU resource requirement, then add
instance user data that sets `--default-runtime nvidia` and restarts Docker,
plus `NVIDIA_VISIBLE_DEVICES` on the container) requires a shell-based AMI such
as Amazon Linux 2. The only AWS-published arm64 + NVIDIA ECS AMI is Bottlerocket,
which has no shell and no bash user data, so that workaround cannot be applied.
There is therefore no managed-compute path that gives a g5g container a GPU.

## Consequences

- No `g5g` entry is added to `PROCESSOR_CONFIGS`; the GPU transcoding family
  stays the x86 `nvidia` processor (G4dn/G5).
- MR !113, which implemented the processor, is closed. The implementation was
  structurally correct (the compute environment is accepted and healthy); it is
  the GPU scheduling that AWS Batch does not support for g5g.
- Revisit if AWS Batch/ECS adds g5g to the GPU instance-family list, or publishes
  a shell-based arm64 GPU ECS-optimized AMI. The reusable finding: a managed
  Batch compute environment accepts a custom Bottlerocket AMI override and the
  g5g instance type; only the GPU device scheduling is missing.
