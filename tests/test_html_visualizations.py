"""Tests for HTML Visualization module."""

from csv_to_mermaid_gantt.html_visualizations import (
    prepare_timeline_data,
    prepare_histogram_data,
    prepare_line_graph_data,
    generate_html_visualization,
    convert_csv_files_to_html,
)


class TestPrepareTimelineData:
    """Tests for prepare_timeline_data function."""

    def test_prepare_timeline_data_basic(self) -> None:
        """Test preparing timeline data from basic tasks."""
        tasks = [
            {
                "task_name": "Task 1",
                "start_date": "2024-01-01",
                "start_time": "10:00:00",
                "end_date": "2024-01-01",
                "end_time": "11:00:00",
            },
            {
                "task_name": "Task 2",
                "start_date": "2024-01-01",
                "start_time": "12:00:00",
                "end_date": "2024-01-01",
                "end_time": "13:00:00",
            },
        ]

        result = prepare_timeline_data(tasks)
        assert len(result) == 2
        assert result[0]["task"] == "Task 1"
        assert "start" in result[0]
        assert "end" in result[0]
        assert "start_ts" in result[0]
        assert "end_ts" in result[0]

    def test_prepare_timeline_data_without_time(self) -> None:
        """Test preparing timeline data without time component."""
        tasks = [
            {
                "task_name": "Task 1",
                "start_date": "2024-01-01",
                "end_date": "2024-01-03",
            }
        ]

        result = prepare_timeline_data(tasks)
        assert len(result) == 1
        assert result[0]["task"] == "Task 1"

    def test_prepare_timeline_data_missing_dates(self) -> None:
        """Test preparing timeline data with missing dates."""
        tasks = [
            {"task_name": "Task 1"},
            {
                "task_name": "Task 2",
                "start_date": "2024-01-01",
                "start_time": "10:00:00",
            },
        ]

        result = prepare_timeline_data(tasks)
        # Only tasks with both start and end should be included
        assert len(result) == 0

    def test_prepare_timeline_data_empty(self) -> None:
        """Test preparing timeline data with empty list."""
        result = prepare_timeline_data([])
        assert result == []


class TestPrepareHistogramData:
    """Tests for prepare_histogram_data function."""

    def test_prepare_histogram_data_basic(self) -> None:
        """Test preparing histogram data from tasks."""
        tasks = [
            {
                "task_name": "Task 1",
                "start_date": "2024-01-01",
                "start_time": "10:00:00",
            },
            {
                "task_name": "Task 2",
                "start_date": "2024-01-01",
                "start_time": "10:30:00",
            },
            {
                "task_name": "Task 3",
                "start_date": "2024-01-01",
                "start_time": "12:00:00",
            },
        ]

        result = prepare_histogram_data(tasks, bin_size_seconds=3600)
        assert "bins" in result
        assert "counts" in result
        assert len(result["bins"]) > 0
        assert len(result["counts"]) > 0
        assert len(result["bins"]) == len(result["counts"])

    def test_prepare_histogram_data_empty(self) -> None:
        """Test preparing histogram data with empty list."""
        result = prepare_histogram_data([])
        assert result["bins"] == []
        assert result["counts"] == []

    def test_prepare_histogram_data_no_timestamps(self) -> None:
        """Test preparing histogram data with no timestamps."""
        tasks = [
            {"task_name": "Task 1"},
            {"task_name": "Task 2"},
        ]

        result = prepare_histogram_data(tasks)
        assert result["bins"] == []
        assert result["counts"] == []

    def test_prepare_histogram_data_custom_bin_size(self) -> None:
        """Test preparing histogram data with custom bin size."""
        tasks = [
            {
                "task_name": "Task 1",
                "start_date": "2024-01-01",
                "start_time": "10:00:00",
            },
            {
                "task_name": "Task 2",
                "start_date": "2024-01-01",
                "start_time": "10:00:30",
            },
        ]

        # Use 60 second bins
        result = prepare_histogram_data(tasks, bin_size_seconds=60)
        assert len(result["bins"]) >= 1
        # Both tasks should be in the same 60-second bin
        assert result["counts"][0] == 2


class TestPrepareLineGraphData:
    """Tests for prepare_line_graph_data function."""

    def test_prepare_line_graph_data_basic(self) -> None:
        """Test preparing line graph data from tasks with duration."""
        tasks = [
            {
                "task_name": "Task 1",
                "start_date": "2024-01-01",
                "start_time": "10:00:00",
                "duration": "5d",
            },
            {
                "task_name": "Task 2",
                "start_date": "2024-01-02",
                "start_time": "10:00:00",
                "duration": "3d",
            },
        ]

        result = prepare_line_graph_data(tasks, value_field="duration")
        assert "timestamps" in result
        assert "values" in result
        assert len(result["timestamps"]) == 2
        assert len(result["values"]) == 2
        assert result["values"][0] == 120.0  # 5 days * 24 hours
        assert result["values"][1] == 72.0  # 3 days * 24 hours

    def test_prepare_line_graph_data_hours(self) -> None:
        """Test preparing line graph data with hours."""
        tasks = [
            {
                "task_name": "Task 1",
                "start_date": "2024-01-01",
                "start_time": "10:00:00",
                "duration": "24h",
            },
            {
                "task_name": "Task 2",
                "start_date": "2024-01-01",
                "start_time": "11:00:00",
                "duration": "0h",
            },
        ]

        result = prepare_line_graph_data(tasks, value_field="duration")
        assert len(result["values"]) == 2
        assert result["values"][0] == 24.0
        assert result["values"][1] == 0.0  # Zero hours should be included

    def test_prepare_line_graph_data_numeric(self) -> None:
        """Test preparing line graph data with plain numeric values."""
        tasks = [
            {
                "task_name": "Task 1",
                "start_date": "2024-01-01",
                "start_time": "10:00:00",
                "value": "100",
            },
            {
                "task_name": "Task 2",
                "start_date": "2024-01-01",
                "start_time": "11:00:00",
                "value": "0",
            },
        ]

        result = prepare_line_graph_data(tasks, value_field="value")
        assert len(result["values"]) == 2
        assert result["values"][0] == 100.0
        assert result["values"][1] == 0.0  # Zero should be included

    def test_prepare_line_graph_data_empty(self) -> None:
        """Test preparing line graph data with empty list."""
        result = prepare_line_graph_data([])
        assert result["timestamps"] == []
        assert result["values"] == []

    def test_prepare_line_graph_data_no_values(self) -> None:
        """Test preparing line graph data with no valid values."""
        tasks = [
            {
                "task_name": "Task 1",
                "start_date": "2024-01-01",
                "start_time": "10:00:00",
            }
        ]

        result = prepare_line_graph_data(tasks, value_field="duration")
        assert result["timestamps"] == []
        assert result["values"] == []

    def test_prepare_line_graph_data_invalid_duration(self) -> None:
        """Test preparing line graph data with invalid duration values."""
        tasks = [
            {
                "task_name": "Task 1",
                "start_date": "2024-01-01",
                "start_time": "10:00:00",
                "duration": "invalid",
            },
            {
                "task_name": "Task 2",
                "start_date": "2024-01-01",
                "start_time": "11:00:00",
                "duration": "XYZd",
            },
            {
                "task_name": "Task 3",
                "start_date": "2024-01-01",
                "start_time": "12:00:00",
                "duration": "ABCh",
            },
            {
                "task_name": "Task 4",
                "start_date": "2024-01-01",
                "start_time": "13:00:00",
                "value": "not_a_number",
            },
        ]

        result = prepare_line_graph_data(tasks, value_field="duration")
        # Invalid values should be skipped
        assert result["timestamps"] == []
        assert result["values"] == []

        # Also test with value field
        result2 = prepare_line_graph_data(tasks, value_field="value")
        assert result2["timestamps"] == []
        assert result2["values"] == []


class TestGenerateHtmlVisualization:
    """Tests for generate_html_visualization function."""

    def test_generate_html_basic(self) -> None:
        """Test generating basic HTML visualization."""
        csv_files_data = [
            {
                "name": "test.csv",
                "tasks": [
                    {
                        "task_name": "Task 1",
                        "start_date": "2024-01-01",
                        "start_time": "10:00:00",
                        "end_date": "2024-01-01",
                        "end_time": "11:00:00",
                    }
                ],
            }
        ]

        result = generate_html_visualization(csv_files_data)
        assert "<!DOCTYPE html>" in result
        assert "<html>" in result
        assert "Plotly" in result
        assert "test.csv" in result
        assert "Timeline Chart" in result
        assert "Event Histogram" in result
        assert "Line Graph" in result

    def test_generate_html_custom_title(self) -> None:
        """Test generating HTML with custom title."""
        csv_files_data = [{"name": "test.csv", "tasks": []}]

        result = generate_html_visualization(csv_files_data, title="Custom Title")
        assert "Custom Title" in result

    def test_generate_html_selective_charts(self) -> None:
        """Test generating HTML with selective charts."""
        csv_files_data = [{"name": "test.csv", "tasks": []}]

        result = generate_html_visualization(
            csv_files_data,
            show_timeline=True,
            show_histogram=False,
            show_line_graph=False,
        )
        assert "Timeline Chart" in result
        assert "Event Histogram" not in result
        assert "Line Graph" not in result

    def test_generate_html_multiple_files(self) -> None:
        """Test generating HTML with multiple CSV files."""
        csv_files_data = [
            {"name": "file1.csv", "tasks": []},
            {"name": "file2.csv", "tasks": []},
            {"name": "file3.csv", "tasks": []},
        ]

        result = generate_html_visualization(csv_files_data)
        assert "file1.csv" in result
        assert "file2.csv" in result
        assert "file3.csv" in result
        assert "Filter by CSV File" in result

    def test_generate_html_filtering_controls(self) -> None:
        """Test that HTML includes filtering controls."""
        csv_files_data = [{"name": "test.csv", "tasks": []}]

        result = generate_html_visualization(csv_files_data)
        assert "Filter by CSV File" in result
        assert "Filter by Task Name" in result
        assert "updateFilters()" in result
        assert "resetFilters()" in result


class TestConvertCsvFilesToHtml:
    """Tests for convert_csv_files_to_html function."""

    def test_convert_single_csv_to_html(self) -> None:
        """Test converting single CSV file to HTML."""
        csv_files = [
            {
                "name": "test.csv",
                "content": """task_name,start_date,end_date
Task 1,2024-01-01,2024-01-03
Task 2,2024-01-04,2024-01-06""",
            }
        ]

        result = convert_csv_files_to_html(csv_files)
        assert "<!DOCTYPE html>" in result
        assert "test.csv" in result

    def test_convert_multiple_csv_to_html(self) -> None:
        """Test converting multiple CSV files to HTML."""
        csv_files = [
            {
                "name": "file1.csv",
                "content": """task_name,start_date,end_date
Task 1,2024-01-01,2024-01-03""",
            },
            {
                "name": "file2.csv",
                "content": """task_name,start_date,end_date
Task 2,2024-01-04,2024-01-06""",
            },
        ]

        result = convert_csv_files_to_html(csv_files)
        assert "file1.csv" in result
        assert "file2.csv" in result

    def test_convert_csv_to_html_with_options(self) -> None:
        """Test converting CSV to HTML with various options."""
        csv_files = [
            {
                "name": "test.csv",
                "content": """Name,start_timestamp,end_timestamp
Task 1,2024-01-01T10:00:00,2024-01-01T11:00:00""",
            }
        ]

        result = convert_csv_files_to_html(
            csv_files,
            title="Custom Title",
            show_timeline=True,
            show_histogram=False,
            show_line_graph=True,
        )
        assert "Custom Title" in result
        assert "Timeline Chart" in result
        assert "Line Graph" in result

    def test_convert_csv_to_html_with_combine_threshold(self) -> None:
        """Test converting CSV to HTML with task combining."""
        csv_files = [
            {
                "name": "test.csv",
                "content": """Name,start_timestamp,end_timestamp
Process,2024-01-01T10:00:00,2024-01-01T10:00:30
Process,2024-01-01T10:01:00,2024-01-01T10:02:00""",
            }
        ]

        result = convert_csv_files_to_html(csv_files, combine_threshold=60)
        assert "<!DOCTYPE html>" in result

    def test_convert_csv_to_html_no_combine(self) -> None:
        """Test converting CSV to HTML without task combining."""
        csv_files = [
            {
                "name": "test.csv",
                "content": """Name,start_timestamp,end_timestamp
Process,2024-01-01T10:00:00,2024-01-01T10:00:30
Process,2024-01-01T10:01:00,2024-01-01T10:02:00""",
            }
        ]

        result = convert_csv_files_to_html(csv_files, combine_threshold=None)
        assert "<!DOCTYPE html>" in result
