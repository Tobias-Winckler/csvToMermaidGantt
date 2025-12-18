"""Tests for CSV to Mermaid Gantt Chart Converter."""

import codecs
import os
import pytest
import tempfile
from csv_to_mermaid_gantt import (
    parse_csv,
    parse_timestamp,
    normalize_task_dict,
    validate_task,
    format_task_id,
    generate_mermaid_gantt,
    convert_csv_to_mermaid,
    main,
)
from io import StringIO
from unittest.mock import patch


class TestParseCSV:
    """Tests for parse_csv function."""

    def test_parse_csv_basic(self) -> None:
        """Test parsing basic CSV content."""
        csv_content = """task_name,start_date,duration
Task 1,2024-01-01,3d
Task 2,2024-01-04,2d"""

        result = parse_csv(csv_content)
        assert len(result) == 2
        assert result[0]["task_name"] == "Task 1"
        assert result[0]["start_date"] == "2024-01-01"
        assert result[0]["duration"] == "3d"

    def test_parse_csv_empty(self) -> None:
        """Test parsing empty CSV content."""
        with pytest.raises(ValueError, match="CSV content is empty"):
            parse_csv("")

    def test_parse_csv_with_status(self) -> None:
        """Test parsing CSV with status field."""
        csv_content = """task_name,start_date,duration,status
Task 1,2024-01-01,3d,active
Task 2,2024-01-04,2d,done"""

        result = parse_csv(csv_content)
        assert len(result) == 2
        assert result[0]["status"] == "active"
        assert result[1]["status"] == "done"

    def test_parse_csv_with_end_date(self) -> None:
        """Test parsing CSV with end_date instead of duration."""
        csv_content = """task_name,start_date,end_date
Task 1,2024-01-01,2024-01-03"""

        result = parse_csv(csv_content)
        assert len(result) == 1
        assert result[0]["end_date"] == "2024-01-03"

    def test_parse_csv_with_empty_rows(self) -> None:
        """Test parsing CSV with empty rows."""
        csv_content = """task_name,start_date,duration
Task 1,2024-01-01,3d

Task 2,2024-01-04,2d"""

        result = parse_csv(csv_content)
        # Empty rows should be skipped
        assert len(result) == 2
        assert result[0]["task_name"] == "Task 1"
        assert result[1]["task_name"] == "Task 2"

    def test_parse_csv_with_all_empty_values(self) -> None:
        """Test parsing CSV with rows that have all empty values."""
        csv_content = """task_name,start_date,duration
Task 1,2024-01-01,3d
,,
Task 2,2024-01-04,2d"""

        result = parse_csv(csv_content)
        # Rows with all empty values should be filtered out
        assert len(result) == 2
        assert result[0]["task_name"] == "Task 1"
        assert result[1]["task_name"] == "Task 2"


class TestParseTimestamp:
    """Tests for parse_timestamp function."""

    def test_parse_unix_timestamp(self) -> None:
        """Test parsing Unix timestamp."""
        dt = parse_timestamp("1704110400")
        assert dt is not None
        assert dt.year == 2024
        assert dt.month == 1
        assert dt.day == 1

    def test_parse_iso8601_with_z(self) -> None:
        """Test parsing ISO 8601 with Z."""
        dt = parse_timestamp("2024-01-01T12:30:45Z")
        assert dt is not None
        assert dt.year == 2024
        assert dt.month == 1
        assert dt.day == 1
        assert dt.hour == 12
        assert dt.minute == 30
        assert dt.second == 45

    def test_parse_iso8601_with_microseconds(self) -> None:
        """Test parsing ISO 8601 with microseconds."""
        dt = parse_timestamp("2024-01-01T12:30:45.123456")
        assert dt is not None
        assert dt.microsecond == 123456

    def test_parse_iso8601_space_separator(self) -> None:
        """Test parsing ISO 8601 with space separator."""
        dt = parse_timestamp("2024-01-01 12:30:45")
        assert dt is not None
        assert dt.hour == 12

    def test_parse_date_only(self) -> None:
        """Test parsing date only."""
        dt = parse_timestamp("2024-01-01")
        assert dt is not None
        assert dt.year == 2024
        assert dt.hour == 0

    def test_parse_empty_string(self) -> None:
        """Test parsing empty string."""
        assert parse_timestamp("") is None
        assert parse_timestamp("  ") is None

    def test_parse_invalid_format(self) -> None:
        """Test parsing invalid format."""
        assert parse_timestamp("invalid") is None


class TestNormalizeTaskDict:
    """Tests for normalize_task_dict function."""

    def test_normalize_name_field(self) -> None:
        """Test normalizing 'Name' to 'task_name'."""
        task = {"Name": "Task 1", "start_timestamp": "2024-01-01T12:00:00"}
        normalized = normalize_task_dict(task)
        assert normalized["task_name"] == "Task 1"
        assert "Name" in normalized  # Original field preserved

    def test_normalize_timestamps(self) -> None:
        """Test normalizing timestamp fields."""
        task = {
            "Name": "Task 1",
            "start_timestamp": "2024-01-01T12:00:00",
            "end_timestamp": "2024-01-01T13:00:00",
        }
        normalized = normalize_task_dict(task)
        assert normalized["start_date"] == "2024-01-01"
        assert normalized["start_time"] == "12:00:00"
        assert normalized["end_date"] == "2024-01-01"
        assert normalized["end_time"] == "13:00:00"

    def test_normalize_unix_timestamps(self) -> None:
        """Test normalizing Unix timestamps."""
        task = {
            "Name": "File Access",
            "start_timestamp": "1704110400",
            "end_timestamp": "1704110460",
        }
        normalized = normalize_task_dict(task)
        assert normalized["task_name"] == "File Access"
        assert "start_date" in normalized
        assert "start_time" in normalized

    def test_normalize_preserves_existing_fields(self) -> None:
        """Test that normalization preserves existing fields."""
        task = {"task_name": "Task 1", "start_date": "2024-01-01", "status": "done"}
        normalized = normalize_task_dict(task)
        assert normalized["task_name"] == "Task 1"
        assert normalized["start_date"] == "2024-01-01"
        assert normalized["status"] == "done"


class TestParseCSVWithTimestamps:
    """Tests for parsing CSV with timestamp format."""

    def test_parse_csv_with_timestamps(self) -> None:
        """Test parsing CSV with Name,start_timestamp,end_timestamp format."""
        csv_content = """Name,start_timestamp,end_timestamp
File Access,2024-01-01T12:00:00,2024-01-01T12:01:00
Network Connection,1704110400,1704110460"""

        result = parse_csv(csv_content)
        assert len(result) == 2
        assert result[0]["task_name"] == "File Access"
        assert result[0]["start_date"] == "2024-01-01"
        assert result[0]["start_time"] == "12:00:00"
        assert result[0]["end_time"] == "12:01:00"

    def test_parse_csv_mixed_formats(self) -> None:
        """Test that legacy format still works."""
        csv_content = """task_name,start_date,duration
Planning,2024-01-01,5d"""

        result = parse_csv(csv_content)
        assert len(result) == 1
        assert result[0]["task_name"] == "Planning"
        assert result[0]["start_date"] == "2024-01-01"
        assert result[0]["duration"] == "5d"


class TestValidateTask:
    """Tests for validate_task function."""

    def test_validate_task_valid(self) -> None:
        """Test validating a valid task."""
        task = {"task_name": "Task 1", "start_date": "2024-01-01"}
        validate_task(task)  # Should not raise

    def test_validate_task_missing_name(self) -> None:
        """Test validating task with missing name."""
        task = {"start_date": "2024-01-01"}
        with pytest.raises(ValueError, match="Missing required field: 'task_name'"):
            validate_task(task)

    def test_validate_task_empty_name(self) -> None:
        """Test validating task with empty name."""
        task = {"task_name": "  ", "start_date": "2024-01-01"}
        with pytest.raises(ValueError, match="Missing required field: 'task_name'"):
            validate_task(task)


class TestFormatTaskId:
    """Tests for format_task_id function."""

    def test_format_task_id_basic(self) -> None:
        """Test formatting basic task name."""
        assert format_task_id("Task 1") == "task_1"

    def test_format_task_id_with_hyphens(self) -> None:
        """Test formatting task name with hyphens."""
        assert format_task_id("Task-Name") == "task_name"

    def test_format_task_id_mixed(self) -> None:
        """Test formatting task name with spaces and hyphens."""
        assert format_task_id("My-Task Name") == "my_task_name"


class TestGenerateMermaidGantt:
    """Tests for generate_mermaid_gantt function."""

    def test_generate_basic(self) -> None:
        """Test generating basic Mermaid Gantt chart."""
        tasks = [{"task_name": "Task 1", "start_date": "2024-01-01", "duration": "3d"}]
        result = generate_mermaid_gantt(tasks)

        assert "gantt" in result
        assert "title Gantt Chart" in result
        assert "dateFormat YYYY-MM-DD" in result
        assert "Task 1 :task_1, 2024-01-01, 3d" in result

    def test_generate_custom_title(self) -> None:
        """Test generating Gantt chart with custom title."""
        tasks = [{"task_name": "Task 1"}]
        result = generate_mermaid_gantt(tasks, "My Project")

        assert "title My Project" in result

    def test_generate_with_status(self) -> None:
        """Test generating Gantt chart with task status."""
        tasks = [
            {
                "task_name": "Task 1",
                "start_date": "2024-01-01",
                "duration": "3d",
                "status": "active",
            },
            {
                "task_name": "Task 2",
                "start_date": "2024-01-04",
                "duration": "2d",
                "status": "done",
            },
        ]
        result = generate_mermaid_gantt(tasks)

        assert "Task 1 :task_1, active, 2024-01-01, 3d" in result
        assert "Task 2 :task_2, done, 2024-01-04, 2d" in result

    def test_generate_with_end_date(self) -> None:
        """Test generating Gantt chart with end_date."""
        tasks = [
            {
                "task_name": "Task 1",
                "start_date": "2024-01-01",
                "end_date": "2024-01-03",
            }
        ]
        result = generate_mermaid_gantt(tasks)

        assert "Task 1 :task_1, 2024-01-01, 2024-01-03" in result

    def test_generate_empty_tasks(self) -> None:
        """Test generating Gantt chart with empty tasks list."""
        with pytest.raises(ValueError, match="No tasks provided"):
            generate_mermaid_gantt([])

    def test_generate_invalid_task(self) -> None:
        """Test generating Gantt chart with invalid task."""
        tasks = [{"start_date": "2024-01-01"}]
        with pytest.raises(ValueError, match="Missing required field"):
            generate_mermaid_gantt(tasks)

    def test_generate_task_name_only(self) -> None:
        """Test generating Gantt chart with task name only."""
        tasks = [{"task_name": "Task 1"}]
        result = generate_mermaid_gantt(tasks)

        assert "Task 1 :task_1" in result

    def test_generate_with_crit_status(self) -> None:
        """Test generating Gantt chart with critical status."""
        tasks = [
            {
                "task_name": "Task 1",
                "start_date": "2024-01-01",
                "duration": "3d",
                "status": "crit",
            }
        ]
        result = generate_mermaid_gantt(tasks)

        assert "Task 1 :task_1, crit, 2024-01-01, 3d" in result

    def test_generate_with_invalid_status(self) -> None:
        """Test generating Gantt chart with invalid status (should ignore)."""
        tasks = [
            {
                "task_name": "Task 1",
                "start_date": "2024-01-01",
                "duration": "3d",
                "status": "invalid",
            }
        ]
        result = generate_mermaid_gantt(tasks)

        # Invalid status should be ignored
        assert "Task 1 :task_1, 2024-01-01, 3d" in result
        assert "invalid" not in result

    def test_generate_with_timestamps(self) -> None:
        """Test generating Gantt chart with timestamp data."""
        tasks = [
            {
                "task_name": "Event 1",
                "start_date": "2024-01-01",
                "start_time": "12:00:00",
                "end_date": "2024-01-01",
                "end_time": "13:00:00",
            }
        ]
        result = generate_mermaid_gantt(tasks)

        assert "dateFormat YYYY-MM-DD HH:mm:ss" in result
        assert "Event 1 :event_1, 2024-01-01 12:00:00, 2024-01-01 13:00:00" in result

    def test_generate_with_end_date_and_duration(self) -> None:
        """Test that end_date takes priority over duration when both present."""
        tasks = [
            {
                "task_name": "Task 1",
                "start_date": "2024-01-01",
                "end_date": "2024-01-05",
                "duration": "10d",
            }
        ]
        result = generate_mermaid_gantt(tasks)

        # Should use end_date, not duration
        assert "Task 1 :task_1, 2024-01-01, 2024-01-05" in result
        assert "10d" not in result

    def test_generate_with_width(self) -> None:
        """Test generating Gantt chart with custom width."""
        tasks = [{"task_name": "Task 1", "start_date": "2024-01-01", "duration": "3d"}]
        result = generate_mermaid_gantt(tasks, width=2000)

        assert "%%{init:" in result
        assert "'gantt': {'useWidth': 2000}" in result
        assert "gantt" in result
        assert "Task 1 :task_1, 2024-01-01, 3d" in result

    def test_generate_without_width(self) -> None:
        """Test generating Gantt chart without width (default behavior)."""
        tasks = [{"task_name": "Task 1", "start_date": "2024-01-01", "duration": "3d"}]
        result = generate_mermaid_gantt(tasks)

        assert "%%{init:" not in result
        assert "gantt" in result
        assert "Task 1 :task_1, 2024-01-01, 3d" in result

    def test_generate_with_invalid_width_too_small(self) -> None:
        """Test generating Gantt chart with width below minimum."""
        tasks = [{"task_name": "Task 1", "start_date": "2024-01-01", "duration": "3d"}]
        with pytest.raises(
            ValueError, match="Width must be an integer between 100 and 10000 pixels"
        ):
            generate_mermaid_gantt(tasks, width=50)

    def test_generate_with_invalid_width_too_large(self) -> None:
        """Test generating Gantt chart with width above maximum."""
        tasks = [{"task_name": "Task 1", "start_date": "2024-01-01", "duration": "3d"}]
        with pytest.raises(
            ValueError, match="Width must be an integer between 100 and 10000 pixels"
        ):
            generate_mermaid_gantt(tasks, width=15000)


class TestConvertCSVToMermaid:
    """Tests for convert_csv_to_mermaid function."""

    def test_convert_basic(self) -> None:
        """Test converting basic CSV to Mermaid."""
        csv_content = """task_name,start_date,duration
Task 1,2024-01-01,3d"""

        result = convert_csv_to_mermaid(csv_content)
        assert "gantt" in result
        assert "Task 1" in result

    def test_convert_with_custom_title(self) -> None:
        """Test converting CSV with custom title."""
        csv_content = """task_name,start_date,duration
Task 1,2024-01-01,3d"""

        result = convert_csv_to_mermaid(csv_content, "My Project")
        assert "title My Project" in result

    def test_convert_forensics_format(self) -> None:
        """Test converting forensics CSV format with timestamps."""
        csv_content = """Name,start_timestamp,end_timestamp
File Access,2024-01-01T12:00:00,2024-01-01T12:01:00
Network Event,1704110400,1704110460"""

        result = convert_csv_to_mermaid(csv_content, "Forensics Timeline")
        assert "title Forensics Timeline" in result
        assert "dateFormat YYYY-MM-DD HH:mm:ss" in result
        assert "File Access" in result
        assert "Network Event" in result

    def test_convert_with_both_end_timestamp_and_duration(self) -> None:
        """Test that end_timestamp takes priority over duration."""
        csv_content = """Name,start_timestamp,end_timestamp,duration
Task 1,2025-12-12 07:59:00,2025-12-12 08:00:21,5d"""

        result = convert_csv_to_mermaid(csv_content)
        assert "gantt" in result
        assert "dateFormat YYYY-MM-DD HH:mm:ss" in result
        # Should use end_timestamp, not duration
        assert "2025-12-12 08:00:21" in result
        assert "5d" not in result

    def test_convert_issue_csv_with_name_header(self) -> None:
        """Test converting CSV from issue with Name header and extra column.

        This test covers the exact scenario from the reported issue where the CSV
        has 'Name' as the header (not 'task_name') and includes an extra column
        (0:01:21) that doesn't have a corresponding header.

        Note: This is intentionally malformed CSV (4 comma-separated values in the
        data row, but only 3 headers). The fourth comma-separated value (0:01:21)
        appears after the third column. Python's csv.DictReader handles this by
        creating a None key for extra values, which we gracefully ignore (see the
        None key filtering in validate_task function at line 171).
        """
        csv_content = """Name,start_timestamp,end_timestamp
updTcpIpConnectState,2025-12-12 07:59:00,2025-12-12 08:00:21,0:01:21"""

        result = convert_csv_to_mermaid(csv_content)
        assert "gantt" in result
        assert "dateFormat YYYY-MM-DD HH:mm:ss" in result
        assert "updTcpIpConnectState" in result
        assert "2025-12-12 07:59:00" in result
        assert "2025-12-12 08:00:21" in result

    def test_convert_issue_csv_with_task_name_header(self) -> None:
        """Test converting CSV from issue with task_name header and extra column.

        This test covers the second scenario from the reported issue where the CSV
        uses 'task_name' as the header and includes an extra column (0:01:21).

        Note: This is intentionally malformed CSV (4 comma-separated values in the
        data row, but only 3 headers). The fourth comma-separated value (0:01:21)
        appears after the third column. Python's csv.DictReader handles this by
        creating a None key for extra values, which we gracefully ignore (see the
        None key filtering in validate_task function at line 171).
        """
        csv_content = """task_name,start_timestamp,end_timestamp
updTcpIpConnectState,2025-12-12 07:59:00,2025-12-12 08:00:21,0:01:21"""

        result = convert_csv_to_mermaid(csv_content)
        assert "gantt" in result
        assert "dateFormat YYYY-MM-DD HH:mm:ss" in result
        assert "updTcpIpConnectState" in result
        assert "2025-12-12 07:59:00" in result
        assert "2025-12-12 08:00:21" in result

    def test_convert_issue_csv_without_extra_column_name_header(self) -> None:
        """Test converting CSV with Name header and no extra column.

        This test ensures that the basic case with just Name, start_timestamp,
        and end_timestamp (3 columns total) works correctly.
        """
        csv_content = """Name,start_timestamp,end_timestamp
updTcpIpConnectState,2025-12-12 07:59:00,2025-12-12 08:00:21"""

        result = convert_csv_to_mermaid(csv_content)
        assert "gantt" in result
        assert "dateFormat YYYY-MM-DD HH:mm:ss" in result
        assert "updTcpIpConnectState" in result
        assert "2025-12-12 07:59:00" in result
        assert "2025-12-12 08:00:21" in result

    def test_convert_issue_csv_without_extra_column_task_name_header(self) -> None:
        """Test converting CSV with task_name header and no extra column.

        This test ensures that the basic case with task_name, start_timestamp,
        and end_timestamp (3 columns total) works correctly.
        """
        csv_content = """task_name,start_timestamp,end_timestamp
updTcpIpConnectState,2025-12-12 07:59:00,2025-12-12 08:00:21"""

        result = convert_csv_to_mermaid(csv_content)
        assert "gantt" in result
        assert "dateFormat YYYY-MM-DD HH:mm:ss" in result
        assert "updTcpIpConnectState" in result
        assert "2025-12-12 07:59:00" in result
        assert "2025-12-12 08:00:21" in result

    def test_convert_with_width(self) -> None:
        """Test converting CSV with custom width."""
        csv_content = """task_name,start_date,duration
Task 1,2024-01-01,3d"""

        result = convert_csv_to_mermaid(csv_content, width=1500)
        assert "%%{init:" in result
        assert "'gantt': {'useWidth': 1500}" in result
        assert "gantt" in result
        assert "Task 1" in result


class TestMain:
    """Tests for main CLI function."""

    def test_main_with_input_file(self) -> None:
        """Test main function with input file."""
        csv_content = """task_name,start_date,duration
Task 1,2024-01-01,3d"""

        with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".csv") as f:
            f.write(csv_content)
            temp_file = f.name

        try:
            with patch("sys.argv", ["csv_to_mermaid_gantt", temp_file]):
                with patch("sys.stdout", new_callable=StringIO) as mock_stdout:
                    main()
                    output = mock_stdout.getvalue()
                    assert "gantt" in output
                    assert "Task 1" in output
        finally:
            os.unlink(temp_file)

    def test_main_with_output_file(self) -> None:
        """Test main function with output file."""
        csv_content = """task_name,start_date,duration
Task 1,2024-01-01,3d"""

        with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".csv") as f:
            f.write(csv_content)
            input_file = f.name

        with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".md") as f:
            output_file = f.name

        try:
            with patch(
                "sys.argv", ["csv_to_mermaid_gantt", input_file, "-o", output_file]
            ):
                main()

                with open(output_file, "r") as f:
                    output = f.read()
                    assert "gantt" in output
                    assert "Task 1" in output
        finally:
            os.unlink(input_file)
            os.unlink(output_file)

    def test_main_with_stdin(self) -> None:
        """Test main function with stdin input."""
        csv_content = """task_name,start_date,duration
Task 1,2024-01-01,3d"""

        with patch("sys.argv", ["csv_to_mermaid_gantt"]):
            with patch("sys.stdin", StringIO(csv_content)):
                with patch("sys.stdout", new_callable=StringIO) as mock_stdout:
                    main()
                    output = mock_stdout.getvalue()
                    assert "gantt" in output
                    assert "Task 1" in output

    def test_main_with_verbose_flag(self) -> None:
        """Test main function with verbose flag."""
        csv_content = """Name,start_timestamp,end_timestamp
Task 1,2024-01-01T12:00:00,2024-01-01T13:00:00"""

        with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".csv") as f:
            f.write(csv_content)
            temp_file = f.name

        try:
            with patch("sys.argv", ["csv_to_mermaid_gantt", temp_file, "--verbose"]):
                with patch("sys.stdout", new_callable=StringIO) as mock_stdout:
                    with patch("sys.stderr", new_callable=StringIO) as mock_stderr:
                        main()
                        output = mock_stdout.getvalue()
                        stderr = mock_stderr.getvalue()
                        assert "gantt" in output
                        assert "Task 1" in output
                        # Check for verbose output in stderr
                        assert "[DEBUG]" in stderr
                        assert "CSV headers detected" in stderr
        finally:
            os.unlink(temp_file)

    def test_main_with_custom_title(self) -> None:
        """Test main function with custom title."""
        csv_content = """task_name,start_date,duration
Task 1,2024-01-01,3d"""

        with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".csv") as f:
            f.write(csv_content)
            temp_file = f.name

        try:
            with patch(
                "sys.argv", ["csv_to_mermaid_gantt", temp_file, "-t", "My Project"]
            ):
                with patch("sys.stdout", new_callable=StringIO) as mock_stdout:
                    main()
                    output = mock_stdout.getvalue()
                    assert "title My Project" in output
        finally:
            os.unlink(temp_file)

    def test_main_file_not_found(self) -> None:
        """Test main function with non-existent file."""
        with patch("sys.argv", ["csv_to_mermaid_gantt", "nonexistent.csv"]):
            with patch("sys.stderr", new_callable=StringIO) as mock_stderr:
                with pytest.raises(SystemExit) as exc_info:
                    main()
                assert exc_info.value.code == 1
                assert "File not found" in mock_stderr.getvalue()

    def test_main_invalid_csv(self) -> None:
        """Test main function with invalid CSV."""
        with patch("sys.argv", ["csv_to_mermaid_gantt"]):
            with patch("sys.stdin", StringIO("")):
                with patch("sys.stderr", new_callable=StringIO) as mock_stderr:
                    with pytest.raises(SystemExit) as exc_info:
                        main()
                    assert exc_info.value.code == 1
                    assert "Error:" in mock_stderr.getvalue()

    def test_main_unexpected_error(self) -> None:
        """Test main function with unexpected error."""
        csv_content = """task_name,start_date,duration
Task 1,2024-01-01,3d"""

        with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".csv") as f:
            f.write(csv_content)
            temp_file = f.name

        try:
            with patch("sys.argv", ["csv_to_mermaid_gantt", temp_file]):
                with patch(
                    "csv_to_mermaid_gantt.convert_csv_to_mermaid",
                    side_effect=RuntimeError("Test error"),
                ):
                    with patch("sys.stderr", new_callable=StringIO) as mock_stderr:
                        with pytest.raises(SystemExit) as exc_info:
                            main()
                        assert exc_info.value.code == 1
                        assert "Unexpected error" in mock_stderr.getvalue()
        finally:
            os.unlink(temp_file)

    @pytest.mark.parametrize(
        "header_name",
        ["task_name", "Name"],
        ids=["task_name_header", "Name_header"],
    )
    def test_main_with_utf8_bom(self, header_name: str) -> None:
        """Test main function with UTF-8 BOM in CSV file."""
        csv_content = f"""{header_name},start_timestamp,end_timestamp
updTcpIpConnectState,2025-12-12 07:59:00,2025-12-12 08:00:21"""

        with tempfile.NamedTemporaryFile(mode="wb", delete=False, suffix=".csv") as f:
            # Write UTF-8 BOM followed by CSV content
            f.write(codecs.BOM_UTF8)
            f.write(csv_content.encode("utf-8"))
            temp_file = f.name

        try:
            with patch("sys.argv", ["csv_to_mermaid_gantt", temp_file]):
                with patch("sys.stdout", new_callable=StringIO) as mock_stdout:
                    main()
                    output = mock_stdout.getvalue()
                    assert "gantt" in output
                    assert "updTcpIpConnectState" in output
                    assert "2025-12-12 07:59:00" in output
                    assert "2025-12-12 08:00:21" in output
        finally:
            os.unlink(temp_file)

    def test_main_with_width_flag(self) -> None:
        """Test main function with width flag."""
        csv_content = """task_name,start_date,duration
Task 1,2024-01-01,3d"""

        with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".csv") as f:
            f.write(csv_content)
            temp_file = f.name

        try:
            with patch("sys.argv", ["csv_to_mermaid_gantt", temp_file, "-w", "2000"]):
                with patch("sys.stdout", new_callable=StringIO) as mock_stdout:
                    main()
                    output = mock_stdout.getvalue()
                    assert "%%{init:" in output
                    assert "'gantt': {'useWidth': 2000}" in output
                    assert "gantt" in output
                    assert "Task 1" in output
        finally:
            os.unlink(temp_file)

    def test_main_with_invalid_width(self) -> None:
        """Test main function with invalid width value."""
        csv_content = """task_name,start_date,duration
Task 1,2024-01-01,3d"""

        with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".csv") as f:
            f.write(csv_content)
            temp_file = f.name

        try:
            with patch("sys.argv", ["csv_to_mermaid_gantt", temp_file, "-w", "50"]):
                with patch("sys.stderr", new_callable=StringIO) as mock_stderr:
                    with pytest.raises(SystemExit) as exc_info:
                        main()
                    assert exc_info.value.code == 1
                    stderr_output = mock_stderr.getvalue()
                    assert (
                        "Width must be an integer between 100 and 10000"
                        in stderr_output
                    )
        finally:
            os.unlink(temp_file)
