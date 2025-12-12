"""Tests for CSV to Mermaid Gantt Chart Converter."""

import pytest
import tempfile
import os
from csv_to_mermaid_gantt import (
    parse_csv,
    validate_task,
    format_task_id,
    generate_mermaid_gantt,
    convert_csv_to_mermaid,
    main,
)
from unittest.mock import patch
from io import StringIO


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


class TestValidateTask:
    """Tests for validate_task function."""

    def test_validate_task_valid(self) -> None:
        """Test validating a valid task."""
        task = {"task_name": "Task 1", "start_date": "2024-01-01"}
        validate_task(task)  # Should not raise

    def test_validate_task_missing_name(self) -> None:
        """Test validating task with missing name."""
        task = {"start_date": "2024-01-01"}
        with pytest.raises(ValueError, match="Missing required field: task_name"):
            validate_task(task)

    def test_validate_task_empty_name(self) -> None:
        """Test validating task with empty name."""
        task = {"task_name": "  ", "start_date": "2024-01-01"}
        with pytest.raises(ValueError, match="Missing required field: task_name"):
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
