# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0
"""POSIX metadata of the directories Amazon S3 Files exposes over NFS.

Amazon S3 Files stores POSIX ownership and permissions as user defined metadata
on each object (`file-owner`, `file-group`, `file-permissions`). A directory
exists in the NFS view only as a zero byte object whose key ends with a slash,
and without those three fields S3 Files presents it as `root:root` with 0755:
any user traverses it, only root creates an entry in it.

The wrapper builds its output path from the S3 key of the output url and calls
`os.makedirs` on its parent (src/wrapper/wrapper.py). The access point attributes
that call to the uid of the container, so a parent directory that carries no
metadata makes it fail with `[Errno 13] Permission denied`. An object written
with the S3 API - by the Fargate variants, which have no file system, or by the
metrics writer - implies its parent directories without materializing them, so
without this module it leaves behind exactly that unwritable tree.

This module is the single source of truth of that materialization, shared by:

- `src/wrapper/wrapper.py`, so every object the platform writes with the S3 API
  leaves behind directories a later job can write in, with no manual step;
- `tests/scripts/s3-posix-dirs.py`, which prepares the output tree of the test
  suite before the integration tests run.

It lives in `src/shared_libraries` because that is the only Python directory the
container images copy next to the wrapper (`COPY shared_libraries/
shared_libraries/` in `src/docker-images/7.0/*/Dockerfile`), and it depends on
nothing but the standard library and botocore, so the CDK application can read
its constant without pulling the wrapper dependencies in.
"""

import logging
import os
from typing import List, Tuple

from botocore.exceptions import ClientError

LOGLEVEL = os.environ.get("LOGLEVEL", "INFO").upper()
logging.basicConfig(level=LOGLEVEL)
logger = logging.getLogger(__name__)

# Value of the `file-permissions` metadata of a directory object, as the
# "Permission values reference" table of
# https://docs.aws.amazon.com/AmazonS3/latest/userguide/s3-files-posix-permissions.html
# defines it: the three high octal digits carry the file type, 0040000 for a
# directory (S_IFDIR) where a regular file carries 0100000, and the three low
# digits carry the mode. 755 gives the owner the write and execute bits
# `os.makedirs` needs to create entries, and leaves group and other with
# traversal only.
#
# The constant is declared here, not in infrastructure/config/batch_config.py,
# because the container images copy this directory and not the CDK code: the
# infrastructure re-exports it (see S3FILES_POSIX_DIRECTORY_MODE) so the value
# the access point view is built with is written once.
POSIX_DIRECTORY_MODE = "0040755"

# Error codes head_object answers with for a key that does not exist.
_MISSING_KEY_CODES = ("404", "NoSuchKey", "NotFound")


def process_owner() -> Tuple[str, str]:
    """Return the POSIX identity of the running process, as S3 metadata values.

    The wrapper stamps the directories it creates with its own uid and gid
    instead of a shared constant: the container runs as `USER ffmpeg`
    (uid 1000, `src/docker-images/7.0/*/Dockerfile`), which is exactly the
    identity the access point enforces, so stamping itself is correct by
    construction, needs no second declaration of 1000 inside the image - the
    container embeds no CDK code and could not read it - and stays correct if
    that uid ever changes.

    Returns:
        tuple[str, str]: The uid and the gid of the process, as strings.
    """
    return str(os.getuid()), str(os.getgid())


def directory_chain(prefix: str) -> List[str]:
    """Return every directory key of a prefix, from the outermost to the prefix
    itself.

    Args:
        prefix (str): Prefix of the directory, with or without a trailing
            slash, for example "tests/media-assets/output/".

    Returns:
        list[str]: The directory keys, each with a trailing slash, for example
            ["tests/", "tests/media-assets/", "tests/media-assets/output/"].
    """
    names = [name for name in prefix.split("/") if name]
    return ["/".join(names[: index + 1]) + "/" for index in range(len(names))]


def ancestor_directories(key: str) -> List[str]:
    """Return every directory key an object key implies, parents first.

    Args:
        key (str): Key of the object, for example "output/sdk/intel/out.mp4".

    Returns:
        list[str]: The directory keys of its ancestors, for example
            ["output/", "output/sdk/", "output/sdk/intel/"]. Empty for a key
            sitting at the root of the bucket.
    """
    names = [name for name in key.split("/") if name]
    return directory_chain("/".join(names[:-1]))


def put_directory(s3_client, bucket: str, key: str, uid: str, gid: str) -> None:
    """Create a directory object carrying its POSIX metadata.

    The call is idempotent: it rewrites the object and its metadata, so a run
    that follows a purge of the prefix restores it.

    Args:
        s3_client: Amazon S3 client.
        bucket (str): Name of the bucket backing the file system.
        key (str): Key of the directory, with a trailing slash.
        uid (str): POSIX user id owning the directory.
        gid (str): POSIX group id owning the directory.
    """
    s3_client.put_object(
        Bucket=bucket,
        Key=key,
        Metadata={
            "file-owner": uid,
            "file-group": gid,
            "file-permissions": POSIX_DIRECTORY_MODE,
        },
    )
    logging.info(
        "Directory s3://%s/%s created with owner %s:%s and permissions %s",
        bucket,
        key,
        uid,
        gid,
        POSIX_DIRECTORY_MODE,
    )


def directory_exists(s3_client, bucket: str, key: str) -> bool:
    """Tell whether a directory object already exists.

    Args:
        s3_client: Amazon S3 client.
        bucket (str): Name of the bucket backing the file system.
        key (str): Key of the directory, with a trailing slash.

    Returns:
        bool: True when the object exists, or when its state cannot be read. An
            unreadable state is reported as existing on purpose: overwriting a
            directory the caller cannot even head would replace metadata set by
            someone else.
    """
    try:
        s3_client.head_object(Bucket=bucket, Key=key)
        return True
    except ClientError as error:
        code = error.response.get("Error", {}).get("Code")
        if code in _MISSING_KEY_CODES:
            return False
        logger.warning(
            "Unable to read the state of the directory s3://%s/%s (%s), leaving it as is",
            bucket,
            key,
            code,
        )
        return True


def ensure_object_directories(s3_client, bucket: str, key: str) -> List[str]:
    """Materialize the missing ancestor directories of an object key.

    Called before writing an object with the S3 API, this is what makes the
    prefix writable for the jobs that will later reach it through the file
    system.

    A directory that already exists as an object is left untouched: the input
    trees are deliberately owned by root (ADR 6, the containers only read the
    assets), and rewriting them here would silently hand them over to the
    identity of the process.

    Args:
        s3_client: Amazon S3 client.
        bucket (str): Name of the bucket backing the file system.
        key (str): Key of the object about to be written.

    Returns:
        list[str]: The directory keys created by this call, parents first.
    """
    uid, gid = process_owner()
    created = []
    for directory in ancestor_directories(key):
        if directory_exists(s3_client, bucket, directory):
            continue
        put_directory(s3_client, bucket, directory, uid, gid)
        created.append(directory)
    return created
