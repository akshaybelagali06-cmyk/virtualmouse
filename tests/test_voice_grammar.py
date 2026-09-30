from core.voice_controller import COMMANDS, build_command_grammar


def test_grammar_contains_all_commands() -> None:
    grammar = build_command_grammar("computer")
    assert len(grammar) == len(COMMANDS) + 3
    for command in COMMANDS:
        assert f"computer {command}" in grammar
    assert "computer search" in grammar
    assert "computer type" in grammar
    assert "[unk]" in grammar
