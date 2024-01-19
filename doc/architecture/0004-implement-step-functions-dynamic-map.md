# 4. Implement Step Functions Dynamic Map

Date: 2023-11-09

## Status

Accepted

## Context

The Alexa Perceptual Technologies team needs to process over 3 million multi-modal files for training a large language model (LLM) that can understand and generate audio in order to launch generative artificial intelligence based customer experiences.
Processing them sequentially on an EC2 instance does not scale.

## Decision

I optimize the solution to reliably process huge volumes of media assets with FFmpeg.
I add AWS Step Functions over AWS Batch.
I configure AWS Step Functions to handle job failures, and service limits.

## Consequences

The solution is able to manage the processing of millions media assets.
