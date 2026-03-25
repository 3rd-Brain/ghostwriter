from app.engine.executor import substitute_variables


def test_substitute_variables_basic():
    result = substitute_variables(
        "Hello {content}, your {brand_voice} is great.",
        {"content": "world", "brand_voice": "tone"},
    )
    assert result == "Hello world, your tone is great."


def test_substitute_variables_missing_key():
    result = substitute_variables(
        "Hello {content}, {unknown} here.",
        {"content": "world"},
    )
    assert result == "Hello world, {unknown} here."


def test_substitute_variables_none_value():
    result = substitute_variables(
        "Hello {content}.",
        {"content": None},
    )
    assert result == "Hello ."


def test_substitute_variables_empty_context():
    result = substitute_variables("No vars here.", {})
    assert result == "No vars here."


def test_substitute_variables_json_in_prompt():
    """Verify that JSON braces in prompts are not affected."""
    prompt = 'Return JSON: {"key": "value"}. Use {content} as input.'
    result = substitute_variables(prompt, {"content": "my data"})
    assert result == 'Return JSON: {"key": "value"}. Use my data as input.'
