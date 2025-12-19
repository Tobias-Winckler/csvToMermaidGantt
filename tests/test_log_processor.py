"""Tests for Log Processor."""

import pytest
from csv_to_mermaid_gantt.log_processor import (
    parse_log_timestamp,
    extract_connection_id,
    parse_log_csv,
    match_connection_events,
    convert_log_to_csv,
)


class TestParseLogTimestamp:
    """Tests for parse_log_timestamp function."""

    def test_parse_valid_timestamp(self) -> None:
        """Test parsing valid timestamp."""
        dt = parse_log_timestamp("18/12/2025", "13.00.54")
        assert dt is not None
        assert dt.year == 2025
        assert dt.month == 12
        assert dt.day == 18
        assert dt.hour == 13
        assert dt.minute == 0
        assert dt.second == 54

    def test_parse_empty_strings(self) -> None:
        """Test parsing empty strings."""
        assert parse_log_timestamp("", "") is None
        assert parse_log_timestamp("18/12/2025", "") is None
        # Empty date now uses default date (1970-01-01)
        # to support logs without Date column
        dt = parse_log_timestamp("", "13.00.54")
        assert dt is not None
        assert dt.year == 1970  # Default year
        assert dt.hour == 13
        assert dt.minute == 0
        assert dt.second == 54

    def test_parse_invalid_format(self) -> None:
        """Test parsing invalid format."""
        assert parse_log_timestamp("invalid", "13.00.54") is None
        assert parse_log_timestamp("18/12/2025", "invalid") is None


class TestExtractConnectionId:
    """Tests for extract_connection_id function."""

    def test_extract_connection_id(self) -> None:
        """Test extracting connection ID."""
        conn_id = extract_connection_id("10.10.0.1:58100", "123.123.123.123:443")
        assert conn_id == "10.10.0.1:58100,123.123.123.123:443"

    def test_extract_connection_id_with_spaces(self) -> None:
        """Test extracting connection ID with spaces."""
        conn_id = extract_connection_id(" 10.10.0.1:58100 ", " 123.123.123.123:443 ")
        assert conn_id == "10.10.0.1:58100,123.123.123.123:443"


class TestParseLogCsv:
    """Tests for parse_log_csv function."""

    def test_parse_basic_log(self) -> None:
        """Test parsing basic log CSV."""
        csv_content = """Date,Time,Action,Process,Protocol,LocalAddr,RemoteAddr
18/12/2025,13.00.54,Added,processName.exe,TCP,10.10.0.1:58100,123.123.123.123:443"""

        result = parse_log_csv(csv_content)
        assert len(result) == 1
        assert result[0]["Date"] == "18/12/2025"
        assert result[0]["Time"] == "13.00.54"
        assert result[0]["Action"] == "Added"
        assert result[0]["Process"] == "processName.exe"

    def test_parse_empty_csv(self) -> None:
        """Test parsing empty CSV."""
        with pytest.raises(ValueError, match="CSV content is empty"):
            parse_log_csv("")

    def test_parse_log_with_empty_rows(self) -> None:
        """Test parsing log with empty rows."""
        csv_content = """Date,Time,Action,Process,Protocol,LocalAddr,RemoteAddr
18/12/2025,13.00.54,Added,processName.exe,TCP,10.10.0.1:58100,123.123.123.123:443

18/12/2025,13.00.56,Removed,processName.exe,TCP,10.10.0.1:58100,123.123.123.123:443"""

        result = parse_log_csv(csv_content)
        assert len(result) == 2


class TestMatchConnectionEvents:
    """Tests for match_connection_events function."""

    def test_match_complete_connection(self) -> None:
        """Test matching a complete connection with 2 Added and 2 Removed events."""
        log_entries = [
            {
                "Date": "18/12/2025",
                "Time": "13.00.54",
                "Action": "Added",
                "Process": "processName.exe",
                "Protocol": "TCP",
                "LocalAddr": "10.10.0.1:58100",
                "RemoteAddr": "123.123.123.123:443",
            },
            {
                "Date": "18/12/2025",
                "Time": "13.00.56",
                "Action": "Added",
                "Process": "Unknown",
                "Protocol": "TCP",
                "LocalAddr": "10.10.0.1:58100",
                "RemoteAddr": "123.123.123.123:443",
            },
            {
                "Date": "18/12/2025",
                "Time": "13.00.56",
                "Action": "Removed",
                "Process": "processName.exe",
                "Protocol": "TCP",
                "LocalAddr": "10.10.0.1:58100",
                "RemoteAddr": "123.123.123.123:443",
            },
            {
                "Date": "18/12/2025",
                "Time": "13.02.55",
                "Action": "Removed",
                "Process": "Unknown",
                "Protocol": "TCP",
                "LocalAddr": "10.10.0.1:58100",
                "RemoteAddr": "123.123.123.123:443",
            },
        ]

        result = match_connection_events(log_entries)
        assert len(result) == 1
        assert "processName.exe" in result[0]["Name"]
        assert result[0]["start_timestamp"] == "2025-12-18 13:00:54"
        assert result[0]["end_timestamp"] == "2025-12-18 13:02:55"

    def test_match_incomplete_removed_only(self) -> None:
        """Test handling connection with only Removed events
        (started before logging)."""
        log_entries = [
            {
                "Date": "18/12/2025",
                "Time": "13.00.56",
                "Action": "Removed",
                "Process": "processName.exe",
                "Protocol": "TCP",
                "LocalAddr": "10.10.0.1:58100",
                "RemoteAddr": "123.123.123.123:443",
            },
            {
                "Date": "18/12/2025",
                "Time": "13.02.55",
                "Action": "Removed",
                "Process": "Unknown",
                "Protocol": "TCP",
                "LocalAddr": "10.10.0.1:58100",
                "RemoteAddr": "123.123.123.123:443",
            },
        ]

        result = match_connection_events(log_entries)
        assert len(result) == 1
        assert "processName.exe" in result[0]["Name"]
        # Both timestamps should be the earliest Removed event
        assert result[0]["start_timestamp"] == "2025-12-18 13:00:56"
        assert result[0]["end_timestamp"] == "2025-12-18 13:02:55"

    def test_match_incomplete_added_only(self) -> None:
        """Test handling connection with only Added events (ongoing at log end)."""
        log_entries = [
            {
                "Date": "18/12/2025",
                "Time": "13.00.54",
                "Action": "Added",
                "Process": "processName.exe",
                "Protocol": "TCP",
                "LocalAddr": "10.10.0.1:58100",
                "RemoteAddr": "123.123.123.123:443",
            },
            {
                "Date": "18/12/2025",
                "Time": "13.00.56",
                "Action": "Added",
                "Process": "Unknown",
                "Protocol": "TCP",
                "LocalAddr": "10.10.0.1:58100",
                "RemoteAddr": "123.123.123.123:443",
            },
        ]

        result = match_connection_events(log_entries)
        assert len(result) == 1
        assert "processName.exe" in result[0]["Name"]
        # End timestamp should be same as start (latest Added event)
        assert result[0]["start_timestamp"] == "2025-12-18 13:00:54"
        assert result[0]["end_timestamp"] == "2025-12-18 13:00:54"

    def test_match_connection_reuse(self) -> None:
        """Test handling connection identifier reuse after removal."""
        log_entries = [
            # First connection
            {
                "Date": "18/12/2025",
                "Time": "13.00.54",
                "Action": "Added",
                "Process": "processName.exe",
                "Protocol": "TCP",
                "LocalAddr": "10.10.0.1:58100",
                "RemoteAddr": "123.123.123.123:443",
            },
            {
                "Date": "18/12/2025",
                "Time": "13.00.56",
                "Action": "Removed",
                "Process": "processName.exe",
                "Protocol": "TCP",
                "LocalAddr": "10.10.0.1:58100",
                "RemoteAddr": "123.123.123.123:443",
            },
            # Second connection (reusing same connection identifier)
            {
                "Date": "18/12/2025",
                "Time": "13.05.00",
                "Action": "Added",
                "Process": "anotherProcess.exe",
                "Protocol": "TCP",
                "LocalAddr": "10.10.0.1:58100",
                "RemoteAddr": "123.123.123.123:443",
            },
            {
                "Date": "18/12/2025",
                "Time": "13.05.30",
                "Action": "Removed",
                "Process": "anotherProcess.exe",
                "Protocol": "TCP",
                "LocalAddr": "10.10.0.1:58100",
                "RemoteAddr": "123.123.123.123:443",
            },
        ]

        result = match_connection_events(log_entries)
        # Should create two separate connections due to reuse detection
        assert len(result) == 2
        # First connection: processName.exe
        assert "processName.exe" in result[0]["Name"]
        assert result[0]["start_timestamp"] == "2025-12-18 13:00:54"
        assert result[0]["end_timestamp"] == "2025-12-18 13:00:56"
        # Second connection: anotherProcess.exe (reusing same identifier)
        assert "anotherProcess.exe" in result[1]["Name"]
        assert result[1]["start_timestamp"] == "2025-12-18 13:05:00"
        assert result[1]["end_timestamp"] == "2025-12-18 13:05:30"

    def test_match_multiple_different_connections(self) -> None:
        """Test matching multiple different connections."""
        log_entries = [
            # Connection 1
            {
                "Date": "18/12/2025",
                "Time": "13.00.54",
                "Action": "Added",
                "Process": "processName.exe",
                "Protocol": "TCP",
                "LocalAddr": "10.10.0.1:58100",
                "RemoteAddr": "123.123.123.123:443",
            },
            {
                "Date": "18/12/2025",
                "Time": "13.00.56",
                "Action": "Removed",
                "Process": "processName.exe",
                "Protocol": "TCP",
                "LocalAddr": "10.10.0.1:58100",
                "RemoteAddr": "123.123.123.123:443",
            },
            # Connection 2
            {
                "Date": "18/12/2025",
                "Time": "13.01.00",
                "Action": "Added",
                "Process": "anotherProcess.exe",
                "Protocol": "TCP",
                "LocalAddr": "10.10.0.1:58101",
                "RemoteAddr": "123.123.123.123:443",
            },
            {
                "Date": "18/12/2025",
                "Time": "13.01.30",
                "Action": "Removed",
                "Process": "anotherProcess.exe",
                "Protocol": "TCP",
                "LocalAddr": "10.10.0.1:58101",
                "RemoteAddr": "123.123.123.123:443",
            },
        ]

        result = match_connection_events(log_entries)
        assert len(result) == 2

    def test_match_unknown_process(self) -> None:
        """Test matching connection with only Unknown process names."""
        log_entries = [
            {
                "Date": "18/12/2025",
                "Time": "13.00.54",
                "Action": "Added",
                "Process": "Unknown",
                "Protocol": "TCP",
                "LocalAddr": "10.10.0.1:58100",
                "RemoteAddr": "123.123.123.123:443",
            },
            {
                "Date": "18/12/2025",
                "Time": "13.00.56",
                "Action": "Removed",
                "Process": "Unknown",
                "Protocol": "TCP",
                "LocalAddr": "10.10.0.1:58100",
                "RemoteAddr": "123.123.123.123:443",
            },
        ]

        result = match_connection_events(log_entries)
        assert len(result) == 1
        assert "Unknown" in result[0]["Name"]

    def test_match_prefer_non_unknown_process(self) -> None:
        """Test that non-Unknown process names are preferred."""
        log_entries = [
            {
                "Date": "18/12/2025",
                "Time": "13.00.54",
                "Action": "Added",
                "Process": "processName.exe",
                "Protocol": "TCP",
                "LocalAddr": "10.10.0.1:58100",
                "RemoteAddr": "123.123.123.123:443",
            },
            {
                "Date": "18/12/2025",
                "Time": "13.00.56",
                "Action": "Added",
                "Process": "Unknown",
                "Protocol": "TCP",
                "LocalAddr": "10.10.0.1:58100",
                "RemoteAddr": "123.123.123.123:443",
            },
        ]

        result = match_connection_events(log_entries)
        assert len(result) == 1
        assert "processName.exe" in result[0]["Name"]
        assert (
            "Unknown" not in result[0]["Name"] or "processName.exe" in result[0]["Name"]
        )


class TestConvertLogToCsv:
    """Tests for convert_log_to_csv function."""

    def test_convert_complete_log(self) -> None:
        """Test converting complete log to CSV."""
        log_content = """Date,Time,Action,Process,Protocol,LocalAddr,RemoteAddr
18/12/2025,13.00.54,Added,processName.exe,TCP,10.10.0.1:58100,123.123.123.123:443
18/12/2025,13.00.56,Added,Unknown,TCP,10.10.0.1:58100,123.123.123.123:443
18/12/2025,13.00.56,Removed,processName.exe,TCP,10.10.0.1:58100,123.123.123.123:443
18/12/2025,13.02.55,Removed,Unknown,TCP,10.10.0.1:58100,123.123.123.123:443"""

        result = convert_log_to_csv(log_content)
        lines = result.split("\n")
        assert lines[0] == "Name,start_timestamp,end_timestamp"
        assert len(lines) == 2
        assert "processName.exe" in lines[1]
        assert "2025-12-18 13:00:54" in lines[1]
        assert "2025-12-18 13:02:55" in lines[1]

    def test_convert_empty_log(self) -> None:
        """Test converting empty log."""
        with pytest.raises(ValueError, match="CSV content is empty"):
            convert_log_to_csv("")

    def test_convert_log_with_incomplete_data(self) -> None:
        """Test converting log with incomplete data."""
        log_content = """Date,Time,Action,Process,Protocol,LocalAddr,RemoteAddr
18/12/2025,13.00.56,Removed,processName.exe,TCP,10.10.0.1:58100,123.123.123.123:443
18/12/2025,13.02.55,Removed,Unknown,TCP,10.10.0.1:58100,123.123.123.123:443"""

        result = convert_log_to_csv(log_content)
        lines = result.split("\n")
        assert len(lines) == 2
        assert "processName.exe" in lines[1]

    def test_convert_log_with_multiple_connections(self) -> None:
        """Test converting log with multiple connections."""
        log_content = (
            "Date,Time,Action,Process,Protocol,LocalAddr,RemoteAddr\n"
            "18/12/2025,13.00.54,Added,processName.exe,TCP,"
            "10.10.0.1:58100,123.123.123.123:443\n"
            "18/12/2025,13.00.56,Removed,processName.exe,TCP,"
            "10.10.0.1:58100,123.123.123.123:443\n"
            "18/12/2025,13.01.00,Added,anotherProcess.exe,TCP,"
            "10.10.0.1:58101,123.123.123.123:443\n"
            "18/12/2025,13.01.30,Removed,anotherProcess.exe,TCP,"
            "10.10.0.1:58101,123.123.123.123:443"
        )

        result = convert_log_to_csv(log_content)
        lines = result.split("\n")
        assert len(lines) == 3  # Header + 2 connections

    def test_parse_log_csv_with_windows_line_endings(self) -> None:
        """Test parsing log CSV with Windows line endings (CRLF)."""
        log_content = (
            "Date,Time,Action,Process,Protocol,LocalAddr,RemoteAddr\r\n"
            "18/12/2025,13.00.54,Added,processName.exe,TCP,"
            "10.10.0.1:58100,123.123.123.123:443\r\n"
        )

        result = parse_log_csv(log_content)
        assert len(result) == 1
        assert result[0]["Date"] == "18/12/2025"
        assert result[0]["Action"] == "Added"

    def test_parse_log_csv_with_header_whitespace(self) -> None:
        """Test parsing log CSV with whitespace in headers."""
        log_content = (
            "Date,Time,Action,Process,Protocol,LocalAddr ,RemoteAddr \n"
            "18/12/2025,13.00.54,Added,processName.exe,TCP,"
            "10.10.0.1:58100,123.123.123.123:443"
        )

        result = parse_log_csv(log_content)
        assert len(result) == 1
        # Headers should be normalized (whitespace stripped)
        assert "LocalAddr" in result[0]
        assert "RemoteAddr" in result[0]
        assert result[0]["LocalAddr"] == "10.10.0.1:58100"
        assert result[0]["RemoteAddr"] == "123.123.123.123:443"

    def test_match_connection_events_with_missing_addresses(self) -> None:
        """Test matching connection events when addresses are missing."""
        log_entries = [
            {
                "Date": "18/12/2025",
                "Time": "13.00.54",
                "Action": "Added",
                "Process": "processName.exe",
                "Protocol": "TCP",
                "LocalAddr": "",  # Missing
                "RemoteAddr": "123.123.123.123:443",
            },
        ]

        result = match_connection_events(log_entries)
        # Should return empty list when addresses are missing
        assert len(result) == 0

    def test_convert_log_to_csv_verbose(self) -> None:
        """Test convert_log_to_csv with verbose logging enabled."""
        import io
        import sys

        log_content = """Date,Time,Action,Process,Protocol,LocalAddr,RemoteAddr
18/12/2025,13.00.54,Added,processName.exe,TCP,10.10.0.1:58100,123.123.123.123:443
18/12/2025,13.00.56,Removed,processName.exe,TCP,10.10.0.1:58100,123.123.123.123:443"""

        # Capture stderr to check verbose output
        old_stderr = sys.stderr
        sys.stderr = io.StringIO()

        try:
            result = convert_log_to_csv(log_content, verbose=True)
            stderr_output = sys.stderr.getvalue()

            # Check that verbose logging occurred
            assert "[DEBUG]" in stderr_output
            assert "Parsed" in stderr_output
            assert "Matching connection events" in stderr_output

            # Check that conversion still works
            lines = result.splitlines()
            assert len(lines) == 2  # Header + 1 connection

            # Verify CSV structure
            assert lines[0] == "Name,start_timestamp,end_timestamp"

            # Verify the connection data contains expected elements
            connection_line = lines[1]
            assert "processName.exe" in connection_line
            assert "TCP" in connection_line
            assert "10.10.0.1:58100" in connection_line
            assert "123.123.123.123:443" in connection_line
            assert "2025-12-18 13:00:54" in connection_line
            assert "2025-12-18 13:00:56" in connection_line
        finally:
            sys.stderr = old_stderr

    def test_parse_log_csv_misaligned_columns(self) -> None:
        """Test parsing log CSV with misaligned column counts."""
        # Header has 6 columns but data rows have 7 columns
        log_content = (
            "Time,Action,Process,Protocol,LocalAddr,RemoteAddr\n"
            "18/12/2025,13.00.54,Added,processName.exe,TCP,"
            "10.10.0.1:58100,123.123.123.123:443\n"
            "18/12/2025,13.00.56,Removed,processName.exe,TCP,"
            "10.10.0.1:58100,123.123.123.123:443"
        )

        with pytest.raises(
            ValueError,
            match="CSV structure error.*Header row has 6 columns.*row.*has 7 columns",
        ):
            parse_log_csv(log_content)
