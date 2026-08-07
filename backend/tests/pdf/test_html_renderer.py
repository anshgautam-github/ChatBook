from app.models.conversation import Message, MessageRole, QaSection
from app.pdf.html_renderer import HtmlDocumentBuilder


def _message(content: str, role: MessageRole = MessageRole.USER, order: int = 0) -> Message:
    return Message(id=f"msg-{order}", role=role, content=content, order=order)


class TestCoverPage:
    def test_includes_title_generated_date_and_section_count(self) -> None:
        builder = HtmlDocumentBuilder()
        sections = [
            QaSection(
                id="s1",
                section_index=1,
                question=_message("What is a hash map?"),
                answer=_message("A hash map is...", role=MessageRole.ASSISTANT),
            )
        ]
        html_doc = builder.build(title="My Study Notes", sections=sections)
        assert "<html" in html_doc
        assert "My Study Notes" in html_doc
        assert "1 chapter" in html_doc

    def test_title_is_html_escaped(self) -> None:
        builder = HtmlDocumentBuilder()
        html_doc = builder.build(title="<script>alert(1)</script>", sections=[])
        assert "<script>alert(1)</script>" not in html_doc
        assert "&lt;script&gt;" in html_doc

    def test_missing_title_falls_back_to_default(self) -> None:
        builder = HtmlDocumentBuilder()
        html_doc = builder.build(title="", sections=[])
        assert "Study Notes" in html_doc

    def test_source_url_included_when_provided(self) -> None:
        builder = HtmlDocumentBuilder()
        html_doc = builder.build(title="T", sections=[], source_url="https://chatgpt.com/share/abc")
        assert "https://chatgpt.com/share/abc" in html_doc

    def test_source_url_omitted_when_none(self) -> None:
        builder = HtmlDocumentBuilder()
        html_doc = builder.build(title="T", sections=[], source_url=None)
        # The `.cover-source` CSS rule is always present in the embedded
        # stylesheet; what matters is that the *element* using it isn't
        # rendered when there's no source URL to show.
        assert '<p class="cover-source">' not in html_doc


class TestSequentialSectionNumbering:
    def test_sections_renumber_sequentially_regardless_of_original_section_index(self) -> None:
        """Deselected sections leave gaps in `section_index` (e.g. 1, 4, 9);
        the rendered PDF should renumber 1..N based on list position, not
        reuse the original (gapped) index."""
        builder = HtmlDocumentBuilder()
        sections = [
            QaSection(id="a", section_index=1, question=_message("Q1"), answer=_message("A1", role=MessageRole.ASSISTANT)),
            QaSection(id="b", section_index=4, question=_message("Q2"), answer=_message("A2", role=MessageRole.ASSISTANT)),
            QaSection(id="c", section_index=9, question=_message("Q3"), answer=_message("A3", role=MessageRole.ASSISTANT)),
        ]
        html_doc = builder.build(title="T", sections=sections)
        assert 'id="section-1"' in html_doc
        assert 'id="section-2"' in html_doc
        assert 'id="section-3"' in html_doc
        assert 'id="section-4"' not in html_doc
        assert 'id="section-9"' not in html_doc

    def test_toc_entries_match_rendered_section_anchors(self) -> None:
        builder = HtmlDocumentBuilder()
        sections = [
            QaSection(id="a", section_index=1, question=_message("First question here"), answer=_message("A1", role=MessageRole.ASSISTANT)),
            QaSection(id="b", section_index=2, question=_message("Second question here"), answer=_message("A2", role=MessageRole.ASSISTANT)),
        ]
        html_doc = builder.build(title="T", sections=sections)
        assert 'href="#section-1"' in html_doc
        assert 'href="#section-2"' in html_doc
        assert "First question here" in html_doc
        assert "Second question here" in html_doc


class TestMissingQuestionOrAnswer:
    def test_missing_question_renders_placeholder(self) -> None:
        builder = HtmlDocumentBuilder()
        sections = [
            QaSection(id="a", section_index=1, question=None, answer=_message("Scripted opener", role=MessageRole.ASSISTANT))
        ]
        html_doc = builder.build(title="T", sections=sections)
        assert "No question" in html_doc

    def test_missing_answer_renders_awaiting_placeholder(self) -> None:
        builder = HtmlDocumentBuilder()
        sections = [
            QaSection(id="a", section_index=1, question=_message("Unanswered question"), answer=None)
        ]
        html_doc = builder.build(title="T", sections=sections)
        assert "Awaiting a response" in html_doc


class TestNoSections:
    def test_zero_sections_still_produces_valid_document(self) -> None:
        builder = HtmlDocumentBuilder()
        html_doc = builder.build(title="Empty", sections=[])
        assert "<html" in html_doc
        assert "0 chapter" in html_doc


class TestEndToEndContentPreservation:
    def test_code_table_and_latex_all_render_within_one_section(self) -> None:
        builder = HtmlDocumentBuilder()
        question_content = "How do I sort a list, and what does $E=mc^2$ mean?"
        answer_content = (
            "Here's a sort:\n\n"
            "```python\ndef bubble_sort(items):\n    return sorted(items)\n```\n\n"
            "| Input | Output |\n| --- | --- |\n| [3,1] | [1,3] |\n\n"
            "And the display form: $$a^2 + b^2 = c^2$$\n\n"
            "> Note: this only works for comparable types."
        )
        sections = [
            QaSection(
                id="a",
                section_index=1,
                question=_message(question_content),
                answer=_message(answer_content, role=MessageRole.ASSISTANT),
            )
        ]
        html_doc = builder.build(title="Mixed Content", sections=sections)

        # Code + syntax highlighting
        assert 'class="codehilite"' in html_doc
        assert 'class="nf">bubble_sort<' in html_doc
        # Table
        assert "<table>" in html_doc
        assert "<th>Input</th>" in html_doc
        # LaTeX (either successfully rendered as an image, or gracefully
        # falling back — either way it must not vanish)
        assert ("latex-inline" in html_doc or "latex-fallback" in html_doc)
        assert ("latex-display" in html_doc or "latex-fallback" in html_doc)
        # Note callout
        assert 'class="callout callout--note"' in html_doc
        assert 'class="callout-label"' in html_doc
        assert ">Note<" in html_doc
        # Book-style structure, not a chat transcript
        assert "Prompt 1" in html_doc
        assert 'class="chapter-prompt chapter-copy"' in html_doc
        assert 'class="chapter-body chapter-copy"' in html_doc
        assert "Question" not in html_doc
        assert "Answer" not in html_doc


class TestChapterTitleIsAlwaysPromptN:
    """Chapter titles are deliberately NOT derived from the question's
    content — a derived title looked fine for a short plain-text question,
    but degraded badly for anything else (e.g. a question that's mostly or
    only an image: the "[img not available]" placeholder text itself would
    become the heading). "Prompt N" is short, predictable, and never
    ugly regardless of what the question contains."""

    def test_chapter_title_is_prompt_n_even_for_a_normal_text_question(self) -> None:
        builder = HtmlDocumentBuilder()
        sections = [
            QaSection(
                id="a",
                section_index=1,
                question=_message("What is a hash map and how does it work internally?"),
                answer=_message("A hash map is...", role=MessageRole.ASSISTANT),
            )
        ]
        html_doc = builder.build(title="T", sections=sections)
        assert "<h1 class=\"chapter-title\">Prompt 1</h1>" in html_doc
        # The full question text still renders inside the chapter body —
        # it's just not reused as the heading/TOC label anymore.
        assert "What is a hash map and how does it work internally?" in html_doc

    def test_chapter_title_is_prompt_n_when_question_is_only_an_image_placeholder(self) -> None:
        builder = HtmlDocumentBuilder()
        sections = [
            QaSection(
                id="a",
                section_index=1,
                question=_message("*[img not available]*"),
                answer=_message("From the image, it looks like...", role=MessageRole.ASSISTANT),
            )
        ]
        html_doc = builder.build(title="T", sections=sections)
        assert "<h1 class=\"chapter-title\">Prompt 1</h1>" in html_doc
        assert "img not available" not in html_doc.split("<h1")[1].split("</h1>")[0]

    def test_toc_labels_match_chapter_titles(self) -> None:
        builder = HtmlDocumentBuilder()
        sections = [
            QaSection(id="a", section_index=1, question=_message("Q1"), answer=_message("A1", role=MessageRole.ASSISTANT)),
            QaSection(id="b", section_index=2, question=_message("Q2"), answer=_message("A2", role=MessageRole.ASSISTANT)),
        ]
        html_doc = builder.build(title="T", sections=sections)
        assert "Prompt 1" in html_doc
        assert "Prompt 2" in html_doc
