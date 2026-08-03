# 6. Replace FSx for Lustre with Amazon S3 Files

Date: 2026-07-31

## Status

Accepted

Supersedes [5. Implement FSx Lustre Scratch cluster](0005-implement-fsx-lustre-scratch-cluster.md)

## Context

The shared file system of [ADR 5](0005-implement-fsx-lustre-scratch-cluster.md) is an
FSx for Lustre SCRATCH_2 file system of 1200 GiB. Its capacity is provisioned
permanently and billed permanently, while the workload is intermittent: the file
system exists to serve integration test batches that run a few times a day. The
solution pays for a standing cluster to serve a bursty load.

Three other costs came with it. The Lustre client version had to match the server
version, which tied the solution to a specific AMI generation. Lustre has no
preload API, so an AWS Systems Manager Automation
(`batch-ffmpeg-lustre-preload`) had to boot a throwaway EC2 instance, mount the
file system and run `lfs hsm_restore` before a job could read its input, adding a
stage to the pipeline. And the file system replaced whole on most configuration
changes, which a cross-stack export made impossible until the coordinates of the
file system moved to SSM Parameter Store.

## Decision

Replace the FSx for Lustre file system with Amazon S3 Files, which exposes the
objects of the existing data bucket as an NFS file system.

S3 Files provisions no storage of its own: it is a file system interface onto the
bucket that already holds the media assets, so there is no standing capacity to
bill and no capacity to size. The layer becomes four L1 resources in
`infrastructure/stacks/storage_stack.py`:

- `AWS::S3Files::FileSystem` on the ARN of the data bucket, with the IAM role the
  service assumes to synchronize bucket and file system.
- one `AWS::S3Files::MountTarget` per isolated subnet, since a client can only
  mount through a mount target in its own Availability Zone. Their security group
  accepts TCP 2049 from the VPC CIDR.
- `AWS::S3Files::AccessPoint` enforcing the POSIX identity 1000:1000, the uid of
  the `ffmpeg` user the containers run as.
- `AWS::S3Files::FileSystemPolicy` restricting client access to mounts that go
  through that access point, so no client can mount the root of the file system
  and bypass the enforced identity.

The hosts mount it from their launch template user data
(`infrastructure/constructs/user_data_s3files.txt`) with
`mount -t s3files -o accesspoint=<access point id> <file system id>`. The mount
helper ships in `amazon-efs-utils` 3.0.0 and above and needs the `botocore`
package, both installed from the distribution repository because the compute
subnets have no route to the internet.

The decoupling through SSM Parameter Store is kept: the storage stack publishes
`/batch-ffmpeg/s3files/file-system-id` and
`/batch-ffmpeg/s3files/access-point-id`, and the user data resolves them at boot.
No stack imports an attribute of the file system, so CloudFormation is free to
replace it.

The preload Automation and its document are deleted. S3 Files has no HSM tier to
restore from: the objects of the bucket are visible as files without any prior
action.

## Consequences

The permanently provisioned 1200 GiB disappear from the bill. Two interface VPC
endpoints appear instead — AWS STS and the S3 Files control plane
(`aws.api.<region>.s3files`) — which the mount helper calls and which the
isolated subnets did not have. Their cost is an order of magnitude below the
scratch cluster they replace.

Writes are visible in the bucket asynchronously, in about 30 to 60 seconds.
Anything that reads an output object immediately after a job ends has to wait for
that window. This is not a property the file system being replaced provided
either: the Lustre Data Repository Association carried an `AutoExportPolicy` on
the `NEW`, `CHANGED` and `DELETED` events, so it too exported on its own schedule
after the write. What the shared file system buys is the absence of a copy to
local storage on either side of the job, which is what ADR 5 asked for, and that
is unchanged.

An integration test holds that contract to account rather
than assert it: it submits a job on an EC2 compute variant, having first checked
that the job definition really carries `S3FILES_MOUNT_POINT` so the write goes
through the mount and not through the S3 API, then polls the bucket for the
output object with a 300 second budget and logs the delay it measured. On the
first run against the deployed stacks the object appeared 50 seconds after the
job was observed `SUCCEEDED`, with five polls returning nothing before it — a
single `head_object` right after the job would have returned a 404.

Objects written to the bucket outside the file system — which is how the test
assets are uploaded, and how the Fargate variants write their outputs — carry no
POSIX metadata, so S3 Files presents them as `root:root` with 0644, and their
parent directories as `root:root` with 0755. The access point identity 1000:1000
therefore reads them but cannot create entries in a directory that came from S3.

The input assets stay `root:root`: the containers only read them, and leaving
them unwritable by uid 1000 is the point. What has to change hands is every
directory the containers create an entry in. An output key is
`tests/media-assets/output/<scope>/<compute variant>/<file>`, and the wrapper
calls `os.makedirs` on the compute variant directory, so two levels need the
metadata: the output prefix `tests/media-assets/output/` and each of its scope
directories, one per family of integration tests. The test harness
creates them as zero byte objects whose keys end with a slash, carrying
`file-owner` 1000, `file-group` 1000 and `file-permissions` `0040755` — the
standard directory value
of the [permission reference](https://docs.aws.amazon.com/AmazonS3/latest/userguide/s3-files-posix-permissions.html),
where the high digits `0040000` are the directory file type and 755 gives the
owner the write bit `os.makedirs` needs. The compute variant directories are left
out: the container creates them through the access point, so they already carry
its identity, and nothing else creates an entry in them. The two ancestors of the
output prefix are materialized with the same mode but left `root:root`, which
makes the traversal chain explicit instead of relying on the default S3 Files
applies to a directory that only exists because keys imply it.

The scope level was initially left out too, on the assumption that everything
below the output prefix is created through the access point. The Fargate variants
disprove it: they run without the file system and write their output with the S3
API, so their keys make the scope level appear as a directory that exists only
because keys imply it, `root:root`, and the EC2 variants of the same scope
starting later cannot create their own directory in it. The list of scopes is
declared once, as `Commands.OUTPUT_SCOPES` in
`tests/shared_libraries/commands.py`: `scoped_output_key` rejects a scope missing
from it, the script reads it to know what to create, and
`tests/unit/test_posix_identity.py` parses the integration tests to fail on a
scope used by a test but not declared.

The materialization itself belongs to the platform, not to the test harness: a
user who enables the file system on a fresh output prefix must not have to fix
metadata by hand. The wrapper creates the ancestor directories of every object it
writes with the S3 API — its outputs on the Fargate variants, its quality metrics
in both modes — stamped with the uid and gid of the process, which is the identity
the access point enforces, and leaves an existing directory object untouched so
the root owned input trees keep their ownership.
`src/shared_libraries/s3_posix.py` holds that logic, in the only Python directory
the container images copy next to the wrapper, and the test harness calls the
same functions instead of repeating
them: it only declares the tree the suite needs and stamps 1000:1000 explicitly,
since it runs under the uid of a workstation or a CI runner.

The script runs in `s3:assets:sync`, which fills the bucket, and again at the end
of `integration:data:output:delete`, because the recursive delete of the output
prefix also removes the directory objects of the prefix and of its scopes, and the
two tasks share a pipeline stage.

An alternative was to give the access point `PosixUser` 0:0 and grant
`s3files:ClientRootAccess`, which would let the containers write anywhere. It was
rejected: the container images run as a non root user on purpose, and mapping the
whole file system onto root would undo that.

The client and server version coupling of Lustre is gone: the mount helper is a
package, not a kernel module tied to the file system version.
