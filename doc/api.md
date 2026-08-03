# AWS Batch with FFMPEG : HTTP REST API Documentation

<!--TOC-->

- [AWS Batch with FFMPEG : HTTP REST API Documentation](#aws-batch-with-ffmpeg--http-rest-api-documentation)
- [API Resources](#api-resources)
  - [post__batch_execute_amd](#post__batch_execute_amd)
  - [post__batch_describe](#post__batch_describe)
  - [post__batch_execute_arm](#post__batch_execute_arm)
  - [post__batch_execute_intel](#post__batch_execute_intel)
  - [post__state_execute](#post__state_execute)
  - [post__batch_execute_fargate](#post__batch_execute_fargate)
  - [post__state_describe](#post__state_describe)
  - [post__batch_execute_nvidia](#post__batch_execute_nvidia)
  - [post__batch_execute_fargate-arm](#post__batch_execute_fargate-arm)
- [Schemas](#schemas)

<!--TOC-->

# API Resources


## post__batch_execute_amd

> Code samples

`POST /batch/execute/amd`

> Body parameter

```json
{
  "input_file_options": "string",
  "output_url": "string",
  "name": "string",
  "output_file_options": "string",
  "global_options": "string",
  "instance_type": "string"
}
```

<h3 id="post__batch_execute_amd-parameters">Parameters</h3>

|Name|In|Type|Required|Description|
|---|---|---|---|---|
|body|body|[batchFFmpejIWMTfpPre7F](#schemabatchffmpejiwmtfppre7f)|true|none|
|» input_file_options|body|string|false|none|
|» output_url|body|string|false|none|
|» name|body|string|false|none|
|» output_file_options|body|string|false|none|
|» global_options|body|string|false|none|
|» instance_type|body|string|false|none|

> Example responses

<h3 id="post__batch_execute_amd-responses">Responses</h3>

|Status|Meaning|Description|Schema|
|---|---|---|---|
|200|[OK](https://tools.ietf.org/html/rfc7231#section-6.3.1)|200 response|None|

<h3 id="post__batch_execute_amd-responseschema">Response Schema</h3>

<aside class="warning">
To perform this operation, you must be authenticated by means of one of the following methods:
sigv4
</aside>

## post__batch_describe

> Code samples

`POST /batch/describe`

> Body parameter

```json
{
  "jobId": "string"
}
```

<h3 id="post__batch_describe-parameters">Parameters</h3>

|Name|In|Type|Required|Description|
|---|---|---|---|---|
|body|body|[batchFFmpe5uZPfvUQDlfY](#schemabatchffmpe5uzpfvuqdlfy)|true|none|
|» jobId|body|string|false|none|

> Example responses

<h3 id="post__batch_describe-responses">Responses</h3>

|Status|Meaning|Description|Schema|
|---|---|---|---|
|200|[OK](https://tools.ietf.org/html/rfc7231#section-6.3.1)|200 response|None|

<h3 id="post__batch_describe-responseschema">Response Schema</h3>

<aside class="warning">
To perform this operation, you must be authenticated by means of one of the following methods:
sigv4
</aside>

## post__batch_execute_arm

> Code samples

`POST /batch/execute/arm`

> Body parameter

```json
{
  "input_file_options": "string",
  "output_url": "string",
  "name": "string",
  "output_file_options": "string",
  "global_options": "string",
  "instance_type": "string"
}
```

<h3 id="post__batch_execute_arm-parameters">Parameters</h3>

|Name|In|Type|Required|Description|
|---|---|---|---|---|
|body|body|[batchFFmpejIWMTfpPre7F](#schemabatchffmpejiwmtfppre7f)|true|none|
|» input_file_options|body|string|false|none|
|» output_url|body|string|false|none|
|» name|body|string|false|none|
|» output_file_options|body|string|false|none|
|» global_options|body|string|false|none|
|» instance_type|body|string|false|none|

> Example responses

<h3 id="post__batch_execute_arm-responses">Responses</h3>

|Status|Meaning|Description|Schema|
|---|---|---|---|
|200|[OK](https://tools.ietf.org/html/rfc7231#section-6.3.1)|200 response|None|

<h3 id="post__batch_execute_arm-responseschema">Response Schema</h3>

<aside class="warning">
To perform this operation, you must be authenticated by means of one of the following methods:
sigv4
</aside>

## post__batch_execute_intel

> Code samples

`POST /batch/execute/intel`

> Body parameter

```json
{
  "input_file_options": "string",
  "output_url": "string",
  "name": "string",
  "output_file_options": "string",
  "global_options": "string",
  "instance_type": "string"
}
```

<h3 id="post__batch_execute_intel-parameters">Parameters</h3>

|Name|In|Type|Required|Description|
|---|---|---|---|---|
|body|body|[batchFFmpejIWMTfpPre7F](#schemabatchffmpejiwmtfppre7f)|true|none|
|» input_file_options|body|string|false|none|
|» output_url|body|string|false|none|
|» name|body|string|false|none|
|» output_file_options|body|string|false|none|
|» global_options|body|string|false|none|
|» instance_type|body|string|false|none|

> Example responses

<h3 id="post__batch_execute_intel-responses">Responses</h3>

|Status|Meaning|Description|Schema|
|---|---|---|---|
|200|[OK](https://tools.ietf.org/html/rfc7231#section-6.3.1)|200 response|None|

<h3 id="post__batch_execute_intel-responseschema">Response Schema</h3>

<aside class="warning">
To perform this operation, you must be authenticated by means of one of the following methods:
sigv4
</aside>

## post__state_execute

> Code samples

`POST /state/execute`

> Body parameter

```json
{
  "compute": "string",
  "output": {
    "s3_bucket": "string",
    "file_options": "string",
    "s3_prefix": "string"
  },
  "input": {
    "s3_bucket": "string",
    "file_options": "string",
    "s3_prefix": "string"
  },
  "name": "string",
  "global": {
    "options": "string"
  }
}
```

<h3 id="post__state_execute-parameters">Parameters</h3>

|Name|In|Type|Required|Description|
|---|---|---|---|---|
|body|body|[batchFFmpeXofKstUEQQNT](#schemabatchffmpexofkstueqqnt)|true|none|
|» compute|body|string|false|none|
|» output|body|object|false|none|
|»» s3_bucket|body|string|false|none|
|»» file_options|body|string|false|none|
|»» s3_prefix|body|string|false|none|
|» input|body|object|false|none|
|»» s3_bucket|body|string|false|none|
|»» file_options|body|string|false|none|
|»» s3_prefix|body|string|false|none|
|» name|body|string|false|none|
|» global|body|object|false|none|
|»» options|body|string|false|none|

> Example responses

<h3 id="post__state_execute-responses">Responses</h3>

|Status|Meaning|Description|Schema|
|---|---|---|---|
|200|[OK](https://tools.ietf.org/html/rfc7231#section-6.3.1)|200 response|None|

<h3 id="post__state_execute-responseschema">Response Schema</h3>

<aside class="warning">
To perform this operation, you must be authenticated by means of one of the following methods:
sigv4
</aside>

## post__batch_execute_fargate

> Code samples

`POST /batch/execute/fargate`

> Body parameter

```json
{
  "input_file_options": "string",
  "output_url": "string",
  "name": "string",
  "output_file_options": "string",
  "global_options": "string",
  "instance_type": "string"
}
```

<h3 id="post__batch_execute_fargate-parameters">Parameters</h3>

|Name|In|Type|Required|Description|
|---|---|---|---|---|
|body|body|[batchFFmpejIWMTfpPre7F](#schemabatchffmpejiwmtfppre7f)|true|none|
|» input_file_options|body|string|false|none|
|» output_url|body|string|false|none|
|» name|body|string|false|none|
|» output_file_options|body|string|false|none|
|» global_options|body|string|false|none|
|» instance_type|body|string|false|none|

> Example responses

<h3 id="post__batch_execute_fargate-responses">Responses</h3>

|Status|Meaning|Description|Schema|
|---|---|---|---|
|200|[OK](https://tools.ietf.org/html/rfc7231#section-6.3.1)|200 response|None|

<h3 id="post__batch_execute_fargate-responseschema">Response Schema</h3>

<aside class="warning">
To perform this operation, you must be authenticated by means of one of the following methods:
sigv4
</aside>

## post__state_describe

> Code samples

`POST /state/describe`

> Body parameter

```json
{
  "executionArn": "string"
}
```

<h3 id="post__state_describe-parameters">Parameters</h3>

|Name|In|Type|Required|Description|
|---|---|---|---|---|
|body|body|[batchFFmpev7PQYQAn4VdF](#schemabatchffmpev7pqyqan4vdf)|true|none|
|» executionArn|body|string|false|none|

> Example responses

<h3 id="post__state_describe-responses">Responses</h3>

|Status|Meaning|Description|Schema|
|---|---|---|---|
|200|[OK](https://tools.ietf.org/html/rfc7231#section-6.3.1)|200 response|None|

<h3 id="post__state_describe-responseschema">Response Schema</h3>

<aside class="warning">
To perform this operation, you must be authenticated by means of one of the following methods:
sigv4
</aside>

## post__batch_execute_nvidia

> Code samples

`POST /batch/execute/nvidia`

> Body parameter

```json
{
  "input_file_options": "string",
  "output_url": "string",
  "name": "string",
  "output_file_options": "string",
  "global_options": "string",
  "instance_type": "string"
}
```

<h3 id="post__batch_execute_nvidia-parameters">Parameters</h3>

|Name|In|Type|Required|Description|
|---|---|---|---|---|
|body|body|[batchFFmpejIWMTfpPre7F](#schemabatchffmpejiwmtfppre7f)|true|none|
|» input_file_options|body|string|false|none|
|» output_url|body|string|false|none|
|» name|body|string|false|none|
|» output_file_options|body|string|false|none|
|» global_options|body|string|false|none|
|» instance_type|body|string|false|none|

> Example responses

<h3 id="post__batch_execute_nvidia-responses">Responses</h3>

|Status|Meaning|Description|Schema|
|---|---|---|---|
|200|[OK](https://tools.ietf.org/html/rfc7231#section-6.3.1)|200 response|None|

<h3 id="post__batch_execute_nvidia-responseschema">Response Schema</h3>

<aside class="warning">
To perform this operation, you must be authenticated by means of one of the following methods:
sigv4
</aside>

## post__batch_execute_fargate-arm

> Code samples

`POST /batch/execute/fargate-arm`

> Body parameter

```json
{
  "input_file_options": "string",
  "output_url": "string",
  "name": "string",
  "output_file_options": "string",
  "global_options": "string",
  "instance_type": "string"
}
```

<h3 id="post__batch_execute_fargate-arm-parameters">Parameters</h3>

|Name|In|Type|Required|Description|
|---|---|---|---|---|
|body|body|[batchFFmpejIWMTfpPre7F](#schemabatchffmpejiwmtfppre7f)|true|none|
|» input_file_options|body|string|false|none|
|» output_url|body|string|false|none|
|» name|body|string|false|none|
|» output_file_options|body|string|false|none|
|» global_options|body|string|false|none|
|» instance_type|body|string|false|none|

> Example responses

<h3 id="post__batch_execute_fargate-arm-responses">Responses</h3>

|Status|Meaning|Description|Schema|
|---|---|---|---|
|200|[OK](https://tools.ietf.org/html/rfc7231#section-6.3.1)|200 response|None|

<h3 id="post__batch_execute_fargate-arm-responseschema">Response Schema</h3>

<aside class="warning">
To perform this operation, you must be authenticated by means of one of the following methods:
sigv4
</aside>

# Schemas

<h2 id="tocS_batchFFmpev7PQYQAn4VdF">batchFFmpev7PQYQAn4VdF</h2>
<!-- backwards compatibility -->
<a id="schemabatchffmpev7pqyqan4vdf"></a>
<a id="schema_batchFFmpev7PQYQAn4VdF"></a>
<a id="tocSbatchffmpev7pqyqan4vdf"></a>
<a id="tocsbatchffmpev7pqyqan4vdf"></a>

```json
{
  "executionArn": "string"
}

```

sfn-describe-request-schema

### Properties

|Name|Type|Required|Restrictions|Description|
|---|---|---|---|---|
|executionArn|string|false|none|none|

<h2 id="tocS_batchFFmpejIWMTfpPre7F">batchFFmpejIWMTfpPre7F</h2>
<!-- backwards compatibility -->
<a id="schemabatchffmpejiwmtfppre7f"></a>
<a id="schema_batchFFmpejIWMTfpPre7F"></a>
<a id="tocSbatchffmpejiwmtfppre7f"></a>
<a id="tocsbatchffmpejiwmtfppre7f"></a>

```json
{
  "input_file_options": "string",
  "output_url": "string",
  "name": "string",
  "output_file_options": "string",
  "global_options": "string",
  "instance_type": "string"
}

```

ffmpeg-request-schema

### Properties

|Name|Type|Required|Restrictions|Description|
|---|---|---|---|---|
|input_file_options|string|false|none|none|
|output_url|string|false|none|none|
|name|string|false|none|none|
|output_file_options|string|false|none|none|
|global_options|string|false|none|none|
|instance_type|string|false|none|none|

<h2 id="tocS_batchFFmpeXofKstUEQQNT">batchFFmpeXofKstUEQQNT</h2>
<!-- backwards compatibility -->
<a id="schemabatchffmpexofkstueqqnt"></a>
<a id="schema_batchFFmpeXofKstUEQQNT"></a>
<a id="tocSbatchffmpexofkstueqqnt"></a>
<a id="tocsbatchffmpexofkstueqqnt"></a>

```json
{
  "compute": "string",
  "output": {
    "s3_bucket": "string",
    "file_options": "string",
    "s3_prefix": "string"
  },
  "input": {
    "s3_bucket": "string",
    "file_options": "string",
    "s3_prefix": "string"
  },
  "name": "string",
  "global": {
    "options": "string"
  }
}

```

sfn-request-schema

### Properties

|Name|Type|Required|Restrictions|Description|
|---|---|---|---|---|
|compute|string|false|none|none|
|output|object|false|none|none|
|» s3_bucket|string|false|none|none|
|» file_options|string|false|none|none|
|» s3_prefix|string|false|none|none|
|input|object|false|none|none|
|» s3_bucket|string|false|none|none|
|» file_options|string|false|none|none|
|» s3_prefix|string|false|none|none|
|name|string|false|none|none|
|global|object|false|none|none|
|» options|string|false|none|none|

<h2 id="tocS_batchFFmpe5uZPfvUQDlfY">batchFFmpe5uZPfvUQDlfY</h2>
<!-- backwards compatibility -->
<a id="schemabatchffmpe5uzpfvuqdlfy"></a>
<a id="schema_batchFFmpe5uZPfvUQDlfY"></a>
<a id="tocSbatchffmpe5uzpfvuqdlfy"></a>
<a id="tocsbatchffmpe5uzpfvuqdlfy"></a>

```json
{
  "jobId": "string"
}

```

batch-describe-request-schema

### Properties

|Name|Type|Required|Restrictions|Description|
|---|---|---|---|---|
|jobId|string|false|none|none|
