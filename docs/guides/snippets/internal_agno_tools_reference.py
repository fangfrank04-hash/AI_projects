"""Reference implementation for the internal app.utils.tools module.

Copy the constants and get_agno_model() body into the internal tools.py. This
file is not imported by the local RAGFlow runtime because the local repository
does not contain the internal app/config package layout or the Agno dependency.
"""


AGNO_MAX_OUTPUT_TOKENS = 16384


def _positive_int(value, default):
    try:
        value = int(value)
    except (TypeError, ValueError):
        return default
    return value if value > 0 else default


def get_agno_model(**kwargs):
    from agno.models.openai import OpenAILike

    key = "default"
    if kwargs.get("key"):
        key = kwargs["key"].replace("-", "_")

    model_config = config.chat[key]
    model_name = model_config.llm_name

    # This is the static total context budget from t_model_config.max_tokens.
    # It is not the number of input tokens consumed by the current Agno run.
    total_context_tokens = _positive_int(
        getattr(model_config, "max_tokens", None),
        0,
    )

    requested_output_tokens = _positive_int(
        kwargs.get("max_tokens"),
        AGNO_MAX_OUTPUT_TOKENS,
    )
    max_output_tokens = min(
        requested_output_tokens,
        AGNO_MAX_OUTPUT_TOKENS,
    )

    logger.info(
        "Agno model config: model=%s context_tokens=%s max_output_tokens=%s",
        model_name,
        total_context_tokens,
        max_output_tokens,
    )

    # Never log model_config.api_key or request Authorization headers.
    return OpenAILike(
        id=model_name,
        api_key=model_config.api_key,
        base_url=model_config.api_base,
        default_headers=get_app_serial_number(),
        timeout=kwargs.get("timeout", 120),
        name=model_name,
        max_tokens=max_output_tokens,
        top_p=0.95,
        temperature=0.3,
        extra_body={
            "enable_thinking": True,
        },
    )

