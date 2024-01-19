# AWS Batch with FFMPEG : HTTP REST API Documentation

<!--TOC-->

- [AWS Batch with FFMPEG : HTTP REST API Documentation](#aws-batch-with-ffmpeg--http-rest-api-documentation)
- [API Resources](#api-resources)
  - [post__batch_execute_amd](#post__batch_execute_amd)
  - [post__batch_describe](#post__batch_describe)
  - [post__batch_execute_arm](#post__batch_execute_arm)
  - [post__batch_execute_intel](#post__batch_execute_intel)
  - [post__batch_execute_xilinx](#post__batch_execute_xilinx)
  - [post__state_execute](#post__state_execute)
  - [post__batch_execute_fargate](#post__batch_execute_fargate)
  - [post__state_describe](#post__state_describe)
  - [post__batch_execute_nvidia](#post__batch_execute_nvidia)
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
|body|body|[batchapibaVTMLF9VlVggL](#schemabatchapibavtmlf9vlvggl)|true|none|
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
|body|body|[batchapibaFHUhdMko2D7v](#schemabatchapibafhuhdmko2d7v)|true|none|
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
|body|body|[batchapibaVTMLF9VlVggL](#schemabatchapibavtmlf9vlvggl)|true|none|
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
|body|body|[batchapibaVTMLF9VlVggL](#schemabatchapibavtmlf9vlvggl)|true|none|
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

## post__batch_execute_xilinx

> Code samples

`POST /batch/execute/xilinx`

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

<h3 id="post__batch_execute_xilinx-parameters">Parameters</h3>

|Name|In|Type|Required|Description|
|---|---|---|---|---|
|body|body|[batchapibaVTMLF9VlVggL](#schemabatchapibavtmlf9vlvggl)|true|none|
|» input_file_options|body|string|false|none|
|» output_url|body|string|false|none|
|» name|body|string|false|none|
|» output_file_options|body|string|false|none|
|» global_options|body|string|false|none|
|» instance_type|body|string|false|none|

> Example responses

<h3 id="post__batch_execute_xilinx-responses">Responses</h3>

|Status|Meaning|Description|Schema|
|---|---|---|---|
|200|[OK](https://tools.ietf.org/html/rfc7231#section-6.3.1)|200 response|None|

<h3 id="post__batch_execute_xilinx-responseschema">Response Schema</h3>

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
|body|body|[batchapibaI89Udl8hZZxn](#schemabatchapibai89udl8hzzxn)|true|none|
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
|body|body|[batchapibaVTMLF9VlVggL](#schemabatchapibavtmlf9vlvggl)|true|none|
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
|body|body|[batchapibaHmz4pdHx5R1c](#schemabatchapibahmz4pdhx5r1c)|true|none|
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
|body|body|[batchapibaVTMLF9VlVggL](#schemabatchapibavtmlf9vlvggl)|true|none|
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

# Schemas

<h2 id="tocS_batchapibaI89Udl8hZZxn">batchapibaI89Udl8hZZxn</h2>
<!-- backwards compatibility -->
<a id="schemabatchapibai89udl8hzzxn"></a>
<a id="schema_batchapibaI89Udl8hZZxn"></a>
<a id="tocSbatchapibai89udl8hzzxn"></a>
<a id="tocsbatchapibai89udl8hzzxn"></a>

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

<h2 id="tocS_batchapibaFHUhdMko2D7v">batchapibaFHUhdMko2D7v</h2>
<!-- backwards compatibility -->
<a id="schemabatchapibafhuhdmko2d7v"></a>
<a id="schema_batchapibaFHUhdMko2D7v"></a>
<a id="tocSbatchapibafhuhdmko2d7v"></a>
<a id="tocsbatchapibafhuhdmko2d7v"></a>

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

<h2 id="tocS_batchapibaVTMLF9VlVggL">batchapibaVTMLF9VlVggL</h2>
<!-- backwards compatibility -->
<a id="schemabatchapibavtmlf9vlvggl"></a>
<a id="schema_batchapibaVTMLF9VlVggL"></a>
<a id="tocSbatchapibavtmlf9vlvggl"></a>
<a id="tocsbatchapibavtmlf9vlvggl"></a>

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

<h2 id="tocS_batchapibaHmz4pdHx5R1c">batchapibaHmz4pdHx5R1c</h2>
<!-- backwards compatibility -->
<a id="schemabatchapibahmz4pdhx5r1c"></a>
<a id="schema_batchapibaHmz4pdHx5R1c"></a>
<a id="tocSbatchapibahmz4pdhx5r1c"></a>
<a id="tocsbatchapibahmz4pdhx5r1c"></a>

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
