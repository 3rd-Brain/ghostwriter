from app.providers import resolve_provider, GenerationResult


def substitute_variables(template: str, context: dict) -> str:
    result = template
    for key, value in context.items():
        result = result.replace(f"{{{key}}}", value or "")
    return result


async def execute_workflow(
    steps: list[dict],
    context: dict,
    provider_keys: dict | None = None,
) -> tuple[list[dict], str]:
    """
    Execute workflow steps sequentially.
    Returns tuple of (step_results, final_output).
    """
    prev_output = ""
    step_results = []

    for step in sorted(steps, key=lambda s: s["order"]):
        context["prev_ai_output"] = prev_output

        user_prompt = substitute_variables(step["user_prompt"], context)
        system_prompt = substitute_variables(step["system_prompt"], context)

        provider = resolve_provider(step["model"])

        # Resolve API key: request-level override → system fallback
        api_key = None
        if provider_keys:
            api_key = provider_keys.get(provider.provider_name)

        try:
            result: GenerationResult = await provider.generate(
                model=step["model"],
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                max_tokens=step.get("max_tokens", 4096),
                temperature=step.get("temperature", 0.7),
                api_key=api_key,
            )
        except Exception as e:
            raise RuntimeError(
                f"Workflow step {step['order']} ({step['name']}) failed "
                f"using model {step['model']}: {e}"
            ) from e

        prev_output = result.text
        step_results.append({
            "step": step["order"],
            "name": step["name"],
            "model": step["model"],
            "input_tokens": result.input_tokens,
            "output_tokens": result.output_tokens,
            "output": result.text,
        })

    return step_results, prev_output
