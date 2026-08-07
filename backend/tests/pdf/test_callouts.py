from app.pdf.html_renderer import _apply_callout_styling


class TestPlainBlockquoteBecomesNeutralCallout:
    def test_plain_quote_gets_default_callout_classes(self) -> None:
        html = "<blockquote><p>Just a quotation, no keyword.</p></blockquote>"
        result = _apply_callout_styling(html)
        assert 'class="callout callout--quote"' in result
        assert "callout-label" not in result

    def test_text_is_preserved_for_a_plain_quote(self) -> None:
        html = "<blockquote><p>Just a quotation, no keyword.</p></blockquote>"
        result = _apply_callout_styling(html)
        assert "Just a quotation, no keyword." in result


class TestKeywordDetection:
    def test_note_keyword_is_promoted(self) -> None:
        html = "<blockquote><p>Note: remember to close the connection.</p></blockquote>"
        result = _apply_callout_styling(html)
        assert 'class="callout callout--note"' in result
        assert '<p class="callout-label">Note</p>' in result

    def test_tip_keyword_is_promoted(self) -> None:
        html = "<blockquote><p>Tip: use a context manager instead.</p></blockquote>"
        result = _apply_callout_styling(html)
        assert 'class="callout callout--tip"' in result
        assert '<p class="callout-label">Tip</p>' in result

    def test_warning_keyword_is_promoted(self) -> None:
        html = "<blockquote><p>Warning: this deletes data permanently.</p></blockquote>"
        result = _apply_callout_styling(html)
        assert 'class="callout callout--warning"' in result
        assert '<p class="callout-label">Warning</p>' in result

    def test_caution_and_important_also_map_to_warning_variant(self) -> None:
        for word in ("Caution", "Important"):
            html = f"<blockquote><p>{word}: read this first.</p></blockquote>"
            result = _apply_callout_styling(html)
            assert 'class="callout callout--warning"' in result
            assert f'<p class="callout-label">{word}</p>' in result

    def test_hint_maps_to_tip_variant(self) -> None:
        html = "<blockquote><p>Hint: try a binary search.</p></blockquote>"
        result = _apply_callout_styling(html)
        assert 'class="callout callout--tip"' in result
        assert '<p class="callout-label">Hint</p>' in result

    def test_keyword_is_case_insensitive(self) -> None:
        html = "<blockquote><p>NOTE: case shouldn't matter.</p></blockquote>"
        result = _apply_callout_styling(html)
        assert 'class="callout callout--note"' in result

    def test_leading_keyword_is_stripped_from_body_text(self) -> None:
        html = "<blockquote><p>Note: remember to close the connection.</p></blockquote>"
        result = _apply_callout_styling(html)
        assert "remember to close the connection." in result
        # The keyword only appears once now — as the injected label, not
        # duplicated at the start of the paragraph text.
        assert result.count("Note") == 1

    def test_keyword_only_matches_at_the_very_start(self) -> None:
        """A blockquote that merely mentions 'note' mid-sentence should not
        be mistaken for a labeled callout."""
        html = "<blockquote><p>Please note that this is just a quotation.</p></blockquote>"
        result = _apply_callout_styling(html)
        assert 'class="callout callout--quote"' in result
        assert "callout-label" not in result


class TestNoBlockquotePresent:
    def test_fragment_without_a_blockquote_is_returned_unchanged(self) -> None:
        html = "<p>Nothing to see here.</p>"
        assert _apply_callout_styling(html) == html


class TestMultipleBlockquotes:
    def test_each_blockquote_is_classified_independently(self) -> None:
        html = (
            "<blockquote><p>Tip: cache the result.</p></blockquote>"
            "<p>Some prose in between.</p>"
            "<blockquote><p>Just a citation.</p></blockquote>"
        )
        result = _apply_callout_styling(html)
        assert 'class="callout callout--tip"' in result
        assert 'class="callout callout--quote"' in result
        assert "Some prose in between." in result
