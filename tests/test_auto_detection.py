"""Tests for auto-detection of log columns."""

import pytest
from csv_to_mermaid_gantt.log_processor import (
    parse_log_csv,
    convert_log_to_csv,
    _detect_column_type,
    _is_process_value,
    _is_protocol_value,
    _is_action_value,
    _is_address_value,
    _is_time_value,
    _is_date_value,
)


class TestColumnDetection:
    """Tests for individual column type detection functions."""

    def test_is_process_value(self) -> None:
        """Test process value detection."""
        assert _is_process_value("processName.exe")
        assert _is_process_value("chrome.exe")
        assert _is_process_value("System")
        assert _is_process_value("Unknown")
        assert _is_process_value("svchost")
        assert not _is_process_value("TCP")
        assert not _is_process_value("Added")
        assert not _is_process_value("10.10.0.1:80")
        assert not _is_process_value("")

    def test_is_protocol_value(self) -> None:
        """Test protocol value detection."""
        assert _is_protocol_value("TCP")
        assert _is_protocol_value("UDP")
        assert _is_protocol_value("tcp")  # case insensitive
        assert _is_protocol_value("ICMP")
        assert not _is_protocol_value("Added")
        assert not _is_protocol_value("processName.exe")
        assert not _is_protocol_value("")

    def test_is_action_value(self) -> None:
        """Test action value detection."""
        assert _is_action_value("Added")
        assert _is_action_value("Removed")
        assert not _is_action_value("TCP")
        assert not _is_action_value("added")  # case sensitive
        assert not _is_action_value("")

    def test_is_address_value(self) -> None:
        """Test address value detection."""
        assert _is_address_value("10.10.0.1:80")
        assert _is_address_value("192.168.1.1:443")
        assert _is_address_value("255.255.255.255:65535")
        assert _is_address_value("[::1]:8080")  # IPv6
        assert not _is_address_value("TCP")
        assert not _is_address_value("10.10.0.1")  # no port
        assert not _is_address_value("")

    def test_is_time_value(self) -> None:
        """Test time value detection."""
        assert _is_time_value("13.00.54")
        assert _is_time_value("13:00:54")
        assert _is_time_value("1:30:45")
        assert _is_time_value("13.00.54.123456")  # with microseconds
        assert not _is_time_value("TCP")
        assert not _is_time_value("18/12/2025")
        assert not _is_time_value("")

    def test_is_date_value(self) -> None:
        """Test date value detection."""
        assert _is_date_value("18/12/2025")
        assert _is_date_value("2025-12-18")
        assert _is_date_value("18-12-2025")
        assert _is_date_value("18.12.2025")
        assert not _is_date_value("13.00.54")
        assert not _is_date_value("TCP")
        assert not _is_date_value("")

    def test_detect_column_type_protocol(self) -> None:
        """Test detecting protocol column."""
        values = ["TCP", "TCP", "UDP", "TCP", "UDP"]
        assert _detect_column_type(values) == "Protocol"

    def test_detect_column_type_action(self) -> None:
        """Test detecting action column."""
        values = ["Added", "Added", "Removed", "Removed", "Added"]
        assert _detect_column_type(values) == "Action"

    def test_detect_column_type_address(self) -> None:
        """Test detecting address column."""
        values = ["10.10.0.1:80", "192.168.1.1:443", "10.0.0.1:8080"]
        assert _detect_column_type(values) == "Address"

    def test_detect_column_type_date(self) -> None:
        """Test detecting date column."""
        values = ["18/12/2025", "19/12/2025", "20/12/2025"]
        assert _detect_column_type(values) == "Date"

    def test_detect_column_type_time(self) -> None:
        """Test detecting time column."""
        values = ["13.00.54", "14.30.22", "15.45.10"]
        assert _detect_column_type(values) == "Time"

    def test_detect_column_type_process(self) -> None:
        """Test detecting process column."""
        values = ["chrome.exe", "firefox.exe", "System", "Unknown"]
        assert _detect_column_type(values) == "Process"


class TestAutoDetectionWithMissingHeaders:
    """Tests for parsing logs without headers."""

    def test_parse_log_without_headers(self) -> None:
        """Test parsing log CSV without header row."""
        # Data without headers
        csv_content = (
            "18/12/2025,13.00.54,Added,processName.exe,TCP,"
            "10.10.0.1:58100,123.123.123.123:443\n"
            "18/12/2025,13.00.56,Added,Unknown,TCP,"
            "10.10.0.1:58100,123.123.123.123:443\n"
            "18/12/2025,13.00.56,Removed,processName.exe,TCP,"
            "10.10.0.1:58100,123.123.123.123:443\n"
            "18/12/2025,13.02.55,Removed,Unknown,TCP,"
            "10.10.0.1:58100,123.123.123.123:443"
        )

        result = parse_log_csv(csv_content)
        assert len(result) == 4
        assert result[0]["Action"] == "Added"
        assert result[0]["Process"] == "processName.exe"
        assert result[0]["Protocol"] == "TCP"

    def test_parse_log_missing_date_column(self) -> None:
        """Test parsing log CSV with missing Date column."""
        csv_content = """Time,Action,Process,Protocol,LocalAddr,RemoteAddr
13.00.54,Added,processName.exe,TCP,10.10.0.1:58100,123.123.123.123:443
13.00.56,Added,Unknown,TCP,10.10.0.1:58100,123.123.123.123:443
13.00.56,Removed,processName.exe,TCP,10.10.0.1:58100,123.123.123.123:443
13.02.55,Removed,Unknown,TCP,10.10.0.1:58100,123.123.123.123:443"""

        result = parse_log_csv(csv_content)
        assert len(result) == 4
        assert result[0]["Time"] == "13.00.54"
        assert result[0]["Action"] == "Added"
        assert result[0]["Process"] == "processName.exe"

    def test_parse_log_columns_different_order(self) -> None:
        """Test parsing log CSV with columns in different order."""
        csv_content = """Protocol,Process,Action,Time,RemoteAddr,LocalAddr,Date
TCP,processName.exe,Added,13.00.54,123.123.123.123:443,10.10.0.1:58100,18/12/2025
TCP,Unknown,Added,13.00.56,123.123.123.123:443,10.10.0.1:58100,18/12/2025
TCP,processName.exe,Removed,13.00.56,123.123.123.123:443,10.10.0.1:58100,18/12/2025
TCP,Unknown,Removed,13.02.55,123.123.123.123:443,10.10.0.1:58100,18/12/2025"""

        result = parse_log_csv(csv_content)
        assert len(result) == 4
        assert result[0]["Action"] == "Added"
        assert result[0]["Process"] == "processName.exe"
        assert result[0]["Protocol"] == "TCP"

    def test_convert_log_missing_date_to_csv(self) -> None:
        """Test converting log with missing Date column to CSV format."""
        log_content = (
            "Time,Action,Process,Protocol,LocalAddr,RemoteAddr\n"
            "13.00.54,Added,processName.exe,TCP,"
            "10.10.0.1:58100,123.123.123.123:443\n"
            "13.00.56,Added,Unknown,TCP,"
            "10.10.0.1:58100,123.123.123.123:443\n"
            "13.00.56,Removed,processName.exe,TCP,"
            "10.10.0.1:58100,123.123.123.123:443\n"
            "13.02.55,Removed,Unknown,TCP,"
            "10.10.0.1:58100,123.123.123.123:443"
        )

        result = convert_log_to_csv(log_content)
        lines = result.split("\n")
        assert lines[0] == "Name,start_timestamp,end_timestamp"
        # Header + 1 connection
        assert len(lines) == 2
        assert "processName.exe" in lines[1]

    def test_parse_log_without_headers_different_order(self) -> None:
        """Test parsing without headers with different column order."""
        # Without headers: Protocol, Action, LocalAddr, RemoteAddr,
        # Time, Process
        csv_content = (
            "TCP,Added,10.10.0.1:58100,123.123.123.123:443,"
            "13.00.54,processName.exe\n"
            "TCP,Added,10.10.0.1:58100,123.123.123.123:443,"
            "13.00.56,Unknown\n"
            "TCP,Removed,10.10.0.1:58100,123.123.123.123:443,"
            "13.00.56,processName.exe\n"
            "TCP,Removed,10.10.0.1:58100,123.123.123.123:443,"
            "13.02.55,Unknown"
        )

        result = parse_log_csv(csv_content)
        assert len(result) == 4
        assert result[0]["Action"] == "Added"
        assert result[0]["Protocol"] == "TCP"
        assert result[0]["Process"] == "processName.exe"

    def test_parse_log_ambiguous_data_error(self) -> None:
        """Test that ambiguous data raises an error."""
        # Data that's too ambiguous to auto-detect
        csv_content = """A,B,C,D
value1,value2,value3,value4
data1,data2,data3,data4"""

        with pytest.raises(ValueError, match="Unable to auto-detect"):
            parse_log_csv(csv_content)

    def test_parse_log_partial_headers(self) -> None:
        """Test parsing with some correct headers but missing others."""
        csv_content = """Action,Protocol,Col3,Col4,Col5,Col6
Added,TCP,processName.exe,10.10.0.1:58100,123.123.123.123:443,13.00.54
Removed,TCP,processName.exe,10.10.0.1:58100,123.123.123.123:443,13.02.55"""

        result = parse_log_csv(csv_content)
        assert len(result) == 2
        assert result[0]["Action"] == "Added"
        assert result[0]["Protocol"] == "TCP"


class TestDateTimeFormats:
    """Tests for various date/time format support."""

    def test_parse_log_with_different_time_formats(self) -> None:
        """Test parsing logs with various time formats."""
        from csv_to_mermaid_gantt.log_processor import parse_log_timestamp

        # HH.MM.SS format
        dt1 = parse_log_timestamp("18/12/2025", "13.00.54")
        assert dt1 is not None
        assert dt1.hour == 13
        assert dt1.minute == 0
        assert dt1.second == 54

        # HH:MM:SS format
        dt2 = parse_log_timestamp("18/12/2025", "13:00:54")
        assert dt2 is not None
        assert dt2.hour == 13

    def test_parse_log_with_different_date_formats(self) -> None:
        """Test parsing logs with various date formats."""
        from csv_to_mermaid_gantt.log_processor import parse_log_timestamp

        # DD/MM/YYYY format
        dt1 = parse_log_timestamp("18/12/2025", "13:00:54")
        assert dt1 is not None
        assert dt1.year == 2025
        assert dt1.month == 12
        assert dt1.day == 18

        # YYYY-MM-DD format
        dt2 = parse_log_timestamp("2025-12-18", "13:00:54")
        assert dt2 is not None
        assert dt2.year == 2025

    def test_parse_log_missing_date_uses_default(self) -> None:
        """Test that missing date uses default date."""
        from csv_to_mermaid_gantt.log_processor import parse_log_timestamp

        dt = parse_log_timestamp("", "13:00:54")
        assert dt is not None
        assert dt.year == 1970  # Default year
        assert dt.hour == 13


class TestEndToEnd:
    """End-to-end tests for the complete flow."""

    def test_full_workflow_missing_date(self) -> None:
        """Test complete workflow with missing Date column."""
        log_content = """Time,Action,Process,Protocol,LocalAddr,RemoteAddr
13.00.54,Added,browser.exe,TCP,10.10.0.1:58100,123.123.123.123:443
13.00.56,Added,Unknown,TCP,10.10.0.1:58100,123.123.123.123:443
13.02.56,Removed,browser.exe,TCP,10.10.0.1:58100,123.123.123.123:443
13.02.58,Removed,Unknown,TCP,10.10.0.1:58100,123.123.123.123:443"""

        result = convert_log_to_csv(log_content)
        lines = result.splitlines()

        # Check header
        assert lines[0] == "Name,start_timestamp,end_timestamp"

        # Check we got a connection
        assert len(lines) == 2
        assert "browser.exe" in lines[1]
        assert "TCP" in lines[1]

    def test_full_workflow_columns_different_order(self) -> None:
        """Test complete workflow with columns in different order."""
        log_content = (
            "Process,Protocol,Action,RemoteAddr,LocalAddr,Time,Date\n"
            "server.exe,TCP,Added,192.168.1.100:80,"
            "10.0.0.1:54321,10.30.00,20/12/2025\n"
            "Unknown,TCP,Added,192.168.1.100:80,"
            "10.0.0.1:54321,10.30.01,20/12/2025\n"
            "server.exe,TCP,Removed,192.168.1.100:80,"
            "10.0.0.1:54321,10.35.00,20/12/2025\n"
            "Unknown,TCP,Removed,192.168.1.100:80,"
            "10.0.0.1:54321,10.35.01,20/12/2025"
        )

        result = convert_log_to_csv(log_content)
        lines = result.splitlines()

        assert len(lines) == 2
        assert "server.exe" in lines[1]

    def test_full_workflow_no_headers(self) -> None:
        """Test complete workflow without any headers."""
        # Data in standard order but no header
        log_content = (
            "18/12/2025,13.00.54,Added,myapp.exe,TCP,"
            "10.10.0.1:58100,123.123.123.123:443\n"
            "18/12/2025,13.00.56,Added,Unknown,TCP,"
            "10.10.0.1:58100,123.123.123.123:443\n"
            "18/12/2025,13.02.56,Removed,myapp.exe,TCP,"
            "10.10.0.1:58100,123.123.123.123:443\n"
            "18/12/2025,13.02.58,Removed,Unknown,TCP,"
            "10.10.0.1:58100,123.123.123.123:443"
        )

        result = convert_log_to_csv(log_content)
        lines = result.splitlines()

        assert len(lines) == 2
        assert "myapp.exe" in lines[1]
