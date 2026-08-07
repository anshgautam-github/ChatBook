from app.models.conversation import MessageRole
from app.parsers.conversation_builder import build_conversation
from tests.parsers.fixtures import (
    assistant_message,
    build_conversation_data,
    hidden_message,
    system_message,
    thoughts_message,
    tool_addressed_assistant_message,
    tool_message,
    user_message,
)


class TestBuildConversationBasics:
    def test_title_and_message_order(self) -> None:
        data = build_conversation_data(
            title="My Chat",
            entries=[
                ("sys", system_message("sys")),
                ("n1", user_message("n1", "Question one")),
                ("n2", assistant_message("n2", "Answer one")),
                ("n3", user_message("n3", "Question two")),
                ("n4", assistant_message("n4", "Answer two")),
            ],
        )
        conversation = build_conversation(data, source_url="https://chatgpt.com/share/abc")

        assert conversation.title == "My Chat"
        assert conversation.source_url == "https://chatgpt.com/share/abc"
        assert [m.content for m in conversation.messages] == [
            "Question one",
            "Answer one",
            "Question two",
            "Answer two",
        ]
        assert [m.order for m in conversation.messages] == [0, 1, 2, 3]

    def test_defaults_title_when_missing(self) -> None:
        data = build_conversation_data(title="", entries=[("n1", user_message("n1", "Hi"))])
        conversation = build_conversation(data, source_url="https://chatgpt.com/share/x")
        assert conversation.title == "Untitled Conversation"

    def test_filters_system_tool_and_hidden_messages(self) -> None:
        data = build_conversation_data(
            title="Filtered",
            entries=[
                ("sys", system_message("sys", "you are a helpful assistant")),
                ("n1", user_message("n1", "Question")),
                ("tool1", tool_message("tool1", "tool output")),
                ("tool2", tool_addressed_assistant_message("tool2", "calling a tool")),
                ("hidden1", hidden_message("hidden1", "hidden greeting")),
                ("n2", assistant_message("n2", "Real answer")),
            ],
        )
        conversation = build_conversation(data, source_url="https://chatgpt.com/share/y")
        assert [m.content for m in conversation.messages] == ["Question", "Real answer"]

    def test_filters_hidden_reasoning_content_types(self) -> None:
        data = build_conversation_data(
            title="Reasoning",
            entries=[
                ("n1", user_message("n1", "Question")),
                ("think", thoughts_message("think")),
                ("n2", assistant_message("n2", "Final answer")),
            ],
        )
        conversation = build_conversation(data, source_url="https://chatgpt.com/share/z")
        assert [m.content for m in conversation.messages] == ["Question", "Final answer"]


class TestSectionPairing:
    def test_simple_pairs(self) -> None:
        data = build_conversation_data(
            title="Pairs",
            entries=[
                ("n1", user_message("n1", "Q1")),
                ("n2", assistant_message("n2", "A1")),
                ("n3", user_message("n3", "Q2")),
                ("n4", assistant_message("n4", "A2")),
            ],
        )
        conversation = build_conversation(data, source_url="https://chatgpt.com/share/pairs")

        assert len(conversation.sections) == 2
        assert conversation.sections[0].question.content == "Q1"
        assert conversation.sections[0].answer.content == "A1"
        assert conversation.sections[1].question.content == "Q2"
        assert conversation.sections[1].answer.content == "A2"

    def test_merges_consecutive_assistant_messages(self) -> None:
        data = build_conversation_data(
            title="Continuation",
            entries=[
                ("n1", user_message("n1", "Q1")),
                ("n2", assistant_message("n2", "Part one.")),
                ("n3", assistant_message("n3", "Part two.")),
            ],
        )
        conversation = build_conversation(data, source_url="https://chatgpt.com/share/cont")

        assert len(conversation.sections) == 1
        assert conversation.sections[0].answer.content == "Part one.\n\nPart two."

    def test_trailing_unanswered_question_has_no_answer(self) -> None:
        data = build_conversation_data(
            title="Unanswered",
            entries=[
                ("n1", user_message("n1", "Q1")),
                ("n2", assistant_message("n2", "A1")),
                ("n3", user_message("n3", "Q2 with no reply yet")),
            ],
        )
        conversation = build_conversation(data, source_url="https://chatgpt.com/share/unans")

        assert len(conversation.sections) == 2
        assert conversation.sections[1].question.content == "Q2 with no reply yet"
        assert conversation.sections[1].answer is None

    def test_leading_assistant_only_section_has_no_question(self) -> None:
        data = build_conversation_data(
            title="Scripted opener",
            entries=[
                ("n1", assistant_message("n1", "Hi, I'm a custom GPT, ask me anything!")),
                ("n2", user_message("n2", "Q1")),
                ("n3", assistant_message("n3", "A1")),
            ],
        )
        conversation = build_conversation(data, source_url="https://chatgpt.com/share/opener")

        assert len(conversation.sections) == 2
        assert conversation.sections[0].question is None
        assert conversation.sections[0].answer.content == "Hi, I'm a custom GPT, ask me anything!"
        assert conversation.sections[1].question.content == "Q1"
        assert conversation.sections[1].answer.content == "A1"

    def test_empty_conversation_has_no_messages_or_sections(self) -> None:
        data = build_conversation_data(title="Empty", entries=[])
        conversation = build_conversation(data, source_url="https://chatgpt.com/share/empty")
        assert conversation.messages == []
        assert conversation.sections == []


class TestOrderingFallback:
    def test_falls_back_to_parent_walk_without_linear_conversation(self) -> None:
        data = build_conversation_data(
            title="Tree walk",
            entries=[
                ("n1", user_message("n1", "Q1")),
                ("n2", assistant_message("n2", "A1")),
            ],
            include_linear_conversation=False,
        )
        conversation = build_conversation(data, source_url="https://chatgpt.com/share/tree")
        assert [m.content for m in conversation.messages] == ["Q1", "A1"]
        assert conversation.messages[0].role == MessageRole.USER
        assert conversation.messages[1].role == MessageRole.ASSISTANT
