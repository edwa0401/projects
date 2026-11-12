"""Amazon Bedrock provider using the Converse API with a single structured-output tool.

The model is configurable (BEDROCK_MODEL_ID). Nothing here assumes access to a
particular model: if the model is not enabled, the call fails with a clear,
staff-safe error and the inquiry stays saved for manual handling or retry.
"""

from __future__ import annotations

from ..errors import AnalysisError
from .contract import MODEL_OUTPUT_SCHEMA, TOOL_NAME
from .prompt import SYSTEM_PROMPT, build_user_message
from .provider import ProviderResult

_ERROR_MAP = {
    "AccessDeniedException": ("model_access_denied", "The AI model is not enabled for this AWS account or the function lacks permission. Handle manually; an administrator must enable model access.", False),
    "ResourceNotFoundException": ("model_not_found", "The configured AI model ID was not found in this Region. Handle manually; check BEDROCK_MODEL_ID.", False),
    "ValidationException": ("model_request_invalid", "The AI service rejected the request configuration. Handle manually; an administrator should check the model settings.", False),
    "ThrottlingException": ("model_throttled", "The AI service is busy. Retry in a minute or handle manually.", True),
    "ServiceQuotaExceededException": ("model_throttled", "The AI service quota was reached. Retry later or handle manually.", True),
    "ModelTimeoutException": ("model_timeout", "The AI model took too long to respond. Retry or handle manually.", True),
    "ModelNotReadyException": ("model_not_ready", "The AI model is not ready yet. Retry shortly or handle manually.", True),
    "ServiceUnavailableException": ("model_unavailable", "The AI service is temporarily unavailable. Retry or handle manually.", True),
    "InternalServerException": ("model_unavailable", "The AI service returned an internal error. Retry or handle manually.", True),
    "ModelErrorException": ("model_error", "The AI model returned an error. Retry or handle manually.", True),
}


class BedrockProvider:
    name = "bedrock"

    def __init__(self, config, client=None):
        if not config.bedrock_model_id:
            raise AnalysisError(
                "not_configured",
                "Live AI is selected but BEDROCK_MODEL_ID is not set. Handle manually or configure the model.",
                retryable=False,
            )
        self.model_id = config.bedrock_model_id
        self.max_tokens = config.bedrock_max_tokens
        self.tool_choice = config.bedrock_tool_choice
        self._client = client
        self._config = config

    def _get_client(self):
        if self._client is None:
            import boto3
            from botocore.config import Config as BotoConfig

            self._client = boto3.client(
                "bedrock-runtime",
                region_name=self._config.bedrock_region,
                config=BotoConfig(
                    connect_timeout=5,
                    read_timeout=self._config.bedrock_read_timeout,
                    retries={"max_attempts": 2, "mode": "standard"},
                ),
            )
        return self._client

    def analyze(self, message: str, channel: str, customer: dict) -> ProviderResult:
        tool_choice = {"tool": {"name": TOOL_NAME}} if self.tool_choice == "tool" else {"auto": {}}
        request = {
            "modelId": self.model_id,
            "system": [{"text": SYSTEM_PROMPT}],
            "messages": [{"role": "user", "content": [{"text": build_user_message(message, channel, customer)}]}],
            "inferenceConfig": {"maxTokens": self.max_tokens},
            "toolConfig": {
                "tools": [
                    {
                        "toolSpec": {
                            "name": TOOL_NAME,
                            "description": "Record the structured analysis of one customer inquiry. Has no side effects.",
                            "inputSchema": {"json": MODEL_OUTPUT_SCHEMA},
                        }
                    }
                ],
                "toolChoice": tool_choice,
            },
        }
        try:
            response = self._get_client().converse(**request)
        except Exception as exc:  # map SDK errors to staff-safe messages; never echo raw text
            raise _map_exception(exc) from None

        content = (response.get("output", {}).get("message", {}) or {}).get("content", []) or []
        tool_inputs = [
            block["toolUse"].get("input")
            for block in content
            if isinstance(block, dict) and "toolUse" in block and block["toolUse"].get("name") == TOOL_NAME
        ]
        if len(tool_inputs) != 1 or not isinstance(tool_inputs[0], dict):
            stop = response.get("stopReason")
            code = "model_truncated" if stop == "max_tokens" else "invalid_model_output"
            raise AnalysisError(
                code,
                "The AI did not return a structured analysis. Retry or handle manually.",
                retryable=True,
            )
        usage = response.get("usage", {}) or {}
        return ProviderResult(
            raw=tool_inputs[0],
            model_id=self.model_id,
            input_tokens=usage.get("inputTokens"),
            output_tokens=usage.get("outputTokens"),
        )


def _map_exception(exc: Exception) -> AnalysisError:
    code = None
    response = getattr(exc, "response", None)
    if isinstance(response, dict):
        code = response.get("Error", {}).get("Code")
    if code in _ERROR_MAP:
        c, msg, retry = _ERROR_MAP[code]
        return AnalysisError(c, msg, retry)
    name = type(exc).__name__
    if name in ("NoCredentialsError", "PartialCredentialsError"):
        return AnalysisError("no_credentials", "No AWS credentials are available for the AI service. Handle manually.", False)
    if name in ("ReadTimeoutError", "ConnectTimeoutError"):
        return AnalysisError("model_timeout", "The AI service timed out. Retry or handle manually.", True)
    if name in ("EndpointConnectionError", "ConnectionClosedError"):
        return AnalysisError("model_unreachable", "The AI service could not be reached. Retry or handle manually.", True)
    return AnalysisError("model_error", "The AI analysis failed unexpectedly. Retry or handle manually.", True)
