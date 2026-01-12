"""
Unit tests for LLM parsers module.

Tests JSON parsing, sanitization, and data normalization functions.
"""

import pytest
import json
from src.llm.parsers import (
    sanitize_json_text,
    parse_json_robust,
    normalize_seniority_fields,
    normalize_and_dedupe,
)


class TestSanitizeJsonText:
    """Tests for sanitize_json_text function."""

    def test_remove_code_fences(self):
        """Test that markdown code fences are removed."""
        text = '```json\n{"key": "value"}\n```'
        result = sanitize_json_text(text)
        assert result == '{"key": "value"}'

    def test_remove_code_fences_without_json_label(self):
        """Test removing code fences without 'json' label."""
        text = '```\n{"key": "value"}\n```'
        result = sanitize_json_text(text)
        assert result == '{"key": "value"}'

    def test_replace_smart_quotes(self):
        """Test that smart quotes are replaced with ASCII quotes."""
        text = '{"key": "value"}'  # Contains curly quotes
        result = sanitize_json_text(text)
        assert result == '{"key": "value"}'

    def test_remove_trailing_commas(self):
        """Test that trailing commas before ] and } are removed."""
        text = '{"items": [1, 2, 3,], "last": "value",}'
        result = sanitize_json_text(text)
        assert '3,]' not in result
        assert '"value",}' not in result

    def test_remove_control_characters(self):
        """Test that control characters are removed."""
        text = '{"key": "value\x00\x08\x0B"}'
        result = sanitize_json_text(text)
        assert '\x00' not in result
        assert '\x08' not in result


class TestParseJsonRobust:
    """Tests for parse_json_robust function."""

    def test_parse_valid_json(self):
        """Test parsing valid JSON."""
        text = '{"key": "value", "number": 42}'
        result = parse_json_robust(text)
        assert result == {"key": "value", "number": 42}

    def test_parse_with_code_fences(self):
        """Test parsing JSON wrapped in code fences."""
        text = '```json\n{"key": "value"}\n```'
        result = parse_json_robust(text)
        assert result == {"key": "value"}

    def test_parse_with_trailing_commas(self):
        """Test parsing JSON with trailing commas."""
        text = '{"items": [1, 2, 3,]}'
        result = parse_json_robust(text)
        assert result == {"items": [1, 2, 3]}

    def test_parse_with_extra_text_before(self):
        """Test parsing JSON with text before the object."""
        text = 'Here is the JSON: {"key": "value"}'
        result = parse_json_robust(text)
        assert result == {"key": "value"}

    def test_parse_with_extra_text_after(self):
        """Test parsing JSON with text after the object."""
        text = '{"key": "value"} and some more text'
        result = parse_json_robust(text)
        assert result == {"key": "value"}

    def test_parse_invalid_raises_error(self):
        """Test that completely invalid JSON raises ValueError."""
        text = 'not json at all'
        with pytest.raises(ValueError, match="Unparseable JSON"):
            parse_json_robust(text)

    def test_parse_empty_raises_error(self):
        """Test that empty string raises ValueError."""
        with pytest.raises(ValueError):
            parse_json_robust('')


class TestNormalizeSeniorityFields:
    """Tests for normalize_seniority_fields function."""

    def test_normalize_intern_bucket(self):
        """Test normalizing intern-related buckets."""
        job = {"seniority_bucket": "internship"}
        result = normalize_seniority_fields(job)
        assert result["seniority_bucket"] == "intern"

    def test_normalize_entry_bucket(self):
        """Test normalizing entry-level buckets."""
        for bucket in ["junior", "jr", "new grad", "new_grad"]:
            job = {"seniority_bucket": bucket}
            result = normalize_seniority_fields(job)
            assert result["seniority_bucket"] == "entry"

    def test_normalize_mid_bucket(self):
        """Test normalizing mid-level buckets."""
        for bucket in ["mid-level", "mid level", "midlevel"]:
            job = {"seniority_bucket": bucket}
            result = normalize_seniority_fields(job)
            assert result["seniority_bucket"] == "mid"

    def test_normalize_senior_bucket(self):
        """Test normalizing senior buckets."""
        for bucket in ["sr", "staff", "principal"]:
            job = {"seniority_bucket": bucket}
            result = normalize_seniority_fields(job)
            assert result["seniority_bucket"] == "senior"

    def test_normalize_director_vp_bucket(self):
        """Test normalizing director/VP buckets."""
        for bucket in ["director", "vp", "vice president", "head"]:
            job = {"seniority_bucket": bucket}
            result = normalize_seniority_fields(job)
            assert result["seniority_bucket"] == "director_vp"

    def test_normalize_executive_bucket(self):
        """Test normalizing executive buckets."""
        for bucket in ["cxo", "c-level", "ceo", "cto", "cfo"]:
            job = {"seniority_bucket": bucket}
            result = normalize_seniority_fields(job)
            assert result["seniority_bucket"] == "executive"

    def test_default_to_unknown_bucket(self):
        """Test that invalid buckets default to 'unknown'."""
        job = {"seniority_bucket": "invalid_bucket"}
        result = normalize_seniority_fields(job)
        assert result["seniority_bucket"] == "unknown"

    def test_empty_bucket_defaults_to_unknown(self):
        """Test that empty bucket defaults to 'unknown'."""
        job = {"seniority_bucket": ""}
        result = normalize_seniority_fields(job)
        assert result["seniority_bucket"] == "unknown"

    def test_normalize_seniority_level(self):
        """Test that seniority_level is kept or defaulted."""
        job = {"seniority_bucket": "mid", "seniority_level": "Mid-Level Engineer"}
        result = normalize_seniority_fields(job)
        assert result["seniority_level"] == "Mid-Level Engineer"

    def test_empty_level_defaults_to_unknown(self):
        """Test that empty level defaults to 'Unknown'."""
        job = {"seniority_bucket": "mid", "seniority_level": ""}
        result = normalize_seniority_fields(job)
        assert result["seniority_level"] == "Unknown"


class TestNormalizeAndDedupe:
    """Tests for normalize_and_dedupe function."""

    def test_basic_normalization(self):
        """Test basic data normalization."""
        parsed = {
            "source_url": " https://example.com ",
            "page_title": " Job Listings ",
            "jobs": [
                {"title": "  Software Engineer  ", "job_url": "https://example.com/job1"}
            ]
        }
        result, stats = normalize_and_dedupe(parsed)
        assert result["source_url"] == "https://example.com"
        assert result["page_title"] == "Job Listings"
        assert result["jobs"][0]["title"] == "Software Engineer"

    def test_dedupe_by_url(self):
        """Test deduplication by job_url."""
        parsed = {
            "jobs": [
                {"title": "Engineer", "job_url": "https://example.com/job1"},
                {"title": "Engineer (duplicate)", "job_url": "https://example.com/job1"}
            ]
        }
        result, stats = normalize_and_dedupe(parsed)
        assert stats["input_jobs"] == 2
        assert stats["deduped_out"] == 1
        assert stats["duplicates_removed"] == 1

    def test_dedupe_by_requisition_id(self):
        """Test deduplication by requisition_id."""
        parsed = {
            "jobs": [
                {"title": "Engineer", "requisition_id": "REQ123"},
                {"title": "Engineer", "requisition_id": "REQ123"}
            ]
        }
        result, stats = normalize_and_dedupe(parsed)
        assert stats["deduped_out"] == 1
        assert stats["duplicates_removed"] == 1

    def test_dedupe_by_title_and_location(self):
        """Test deduplication by title + location."""
        parsed = {
            "jobs": [
                {"title": "Engineer", "location": "SF"},
                {"title": "Engineer", "location": "SF"}
            ]
        }
        result, stats = normalize_and_dedupe(parsed)
        assert stats["deduped_out"] == 1

    def test_keeps_richer_version(self):
        """Test that duplicate with more fields is kept."""
        parsed = {
            "jobs": [
                {"title": "Engineer", "job_url": "https://example.com/job1"},
                {
                    "title": "Engineer",
                    "job_url": "https://example.com/job1",
                    "location": "SF",
                    "company": "Acme",
                    "employment_type": "Full-time"
                }
            ]
        }
        result, stats = normalize_and_dedupe(parsed)
        assert stats["deduped_out"] == 1
        kept_job = result["jobs"][0]
        assert "location" in kept_job
        assert "company" in kept_job

    def test_remove_empty_fields(self):
        """Test that empty fields are removed."""
        parsed = {
            "jobs": [
                {
                    "title": "Engineer",
                    "location": "",
                    "company": None,
                    "job_url": "https://example.com/job1"
                }
            ]
        }
        result, stats = normalize_and_dedupe(parsed)
        job = result["jobs"][0]
        assert "location" not in job
        assert "company" not in job
        assert "title" in job

    def test_canonicalize_location_list(self):
        """Test that location list is converted to string."""
        parsed = {
            "jobs": [
                {"title": "Engineer", "location": ["San Francisco", "New York"]}
            ]
        }
        result, stats = normalize_and_dedupe(parsed)
        assert result["jobs"][0]["location"] == "San Francisco, New York"

    def test_normalize_seniority(self):
        """Test that seniority fields are normalized."""
        parsed = {
            "jobs": [
                {"title": "Engineer", "seniority_bucket": "jr", "seniority_level": ""}
            ]
        }
        result, stats = normalize_and_dedupe(parsed)
        job = result["jobs"][0]
        assert job["seniority_bucket"] == "entry"
        assert job["seniority_level"] == "Unknown"

    def test_handle_non_list_jobs(self):
        """Test that non-list jobs field is handled gracefully."""
        parsed = {"jobs": "not a list"}
        result, stats = normalize_and_dedupe(parsed)
        assert result["jobs"] == []
        assert stats["input_jobs"] == 0

    def test_handle_non_dict_job_entries(self):
        """Test that non-dict job entries are skipped."""
        parsed = {
            "jobs": [
                {"title": "Valid Job"},
                "invalid job",
                123,
                None
            ]
        }
        result, stats = normalize_and_dedupe(parsed)
        assert len(result["jobs"]) == 1
        assert result["jobs"][0]["title"] == "Valid Job"

    def test_preserve_order(self):
        """Test that job order is preserved."""
        parsed = {
            "jobs": [
                {"title": "Job A", "job_url": "https://example.com/a"},
                {"title": "Job B", "job_url": "https://example.com/b"},
                {"title": "Job C", "job_url": "https://example.com/c"}
            ]
        }
        result, stats = normalize_and_dedupe(parsed)
        assert result["jobs"][0]["title"] == "Job A"
        assert result["jobs"][1]["title"] == "Job B"
        assert result["jobs"][2]["title"] == "Job C"

    def test_stats_accuracy(self):
        """Test that stats are calculated correctly."""
        parsed = {
            "jobs": [
                {"title": "Job 1", "job_url": "url1"},
                {"title": "Job 2", "job_url": "url2"},
                {"title": "Job 1", "job_url": "url1"},  # duplicate
                {"title": "Job 3", "job_url": "url3"}
            ]
        }
        result, stats = normalize_and_dedupe(parsed)
        assert stats["input_jobs"] == 4
        assert stats["deduped_out"] == 3
        assert stats["duplicates_removed"] == 1
