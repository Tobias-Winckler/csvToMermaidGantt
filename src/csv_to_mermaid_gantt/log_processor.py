"""Log Processor for Network Connection Logs.

This module provides functionality to process network connection logs with
Added/Removed events and convert them to a format compatible with the
diagram visualization tools.

Log format: Date,Time,Action,Process,Protocol,LocalAddr,RemoteAddr
Example: 18/12/2025,13.00.54,Added,processName.exe,TCP,
         10.10.0.1:58100,123.123.123.123:443

Each connection typically has 4 log lines:
- 2 "Added" entries (one for the process, one for Unknown)
- 2 "Removed" entries (one for the process, one for Unknown)

Connections are matched based on: local_ip:local_port,remote_ip:remote_port
"""

import csv
import re
import sys
from datetime import datetime
from typing import List, Dict, Optional, Set


def log_verbose(message: str, verbose: bool = False) -> None:
    """Print verbose logging message if verbose mode is enabled.

    Args:
        message: Message to print
        verbose: Whether to print the message
    """
    if verbose:
        print(f"[DEBUG] {message}", file=sys.stderr)


def _is_protocol_value(value: str) -> bool:
    """Check if value looks like a protocol.

    Args:
        value: Value to check

    Returns:
        True if value matches protocol patterns
    """
    if not value or not value.strip():
        return False
    val = value.strip().upper()
    return val in ["TCP", "UDP", "ICMP", "HTTP", "HTTPS", "FTP", "SSH"]


def _is_action_value(value: str) -> bool:
    """Check if value looks like an action.

    Args:
        value: Value to check

    Returns:
        True if value matches action patterns
    """
    if not value or not value.strip():
        return False
    val = value.strip()
    return val in ["Added", "Removed"]


def _is_address_value(value: str) -> bool:
    """Check if value looks like an IP address with port.

    Args:
        value: Value to check

    Returns:
        True if value matches ip:port pattern
    """
    if not value or not value.strip():
        return False
    val = value.strip()
    # Match ip:port pattern (simple check)
    # IPv4: n.n.n.n:port or IPv6: [xxxx:...]:port
    if ":" in val:
        # Simple IPv4:port check
        if re.match(r"^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}:\d+$", val):
            return True
        # IPv6 with port
        if re.match(r"^\[[\da-fA-F:]+\]:\d+$", val):
            return True
    return False


def _is_time_value(value: str) -> bool:
    """Check if value looks like a time.

    Args:
        value: Value to check

    Returns:
        True if value matches time patterns
    """
    if not value or not value.strip():
        return False
    val = value.strip()
    # Match HH.MM.SS, HH:MM:SS, or HH-MM-SS
    time_patterns = [
        r"^\d{1,2}[.:-]\d{2}[.:-]\d{2}$",  # HH.MM.SS or HH:MM:SS
        r"^\d{1,2}[.:-]\d{2}[.:-]\d{2}\.\d+$",  # with microseconds
    ]
    return any(re.match(pattern, val) for pattern in time_patterns)


def _is_date_value(value: str) -> bool:
    """Check if value looks like a date.

    Args:
        value: Value to check

    Returns:
        True if value matches date patterns
    """
    if not value or not value.strip():
        return False
    val = value.strip()
    # Match DD/MM/YYYY, YYYY-MM-DD, MM-DD-YYYY etc.
    date_patterns = [
        r"^\d{1,2}/\d{1,2}/\d{4}$",  # DD/MM/YYYY or MM/DD/YYYY
        r"^\d{4}-\d{2}-\d{2}$",  # YYYY-MM-DD
        r"^\d{2}-\d{2}-\d{4}$",  # DD-MM-YYYY or MM-DD-YYYY
        r"^\d{1,2}\.\d{1,2}\.\d{4}$",  # DD.MM.YYYY
    ]
    return any(re.match(pattern, val) for pattern in date_patterns)


def _is_process_value(value: str) -> bool:
    """Check if value looks like a process name.

    Args:
        value: Value to check

    Returns:
        True if value matches process name patterns
    """
    if not value or not value.strip():
        return False
    val = value.strip()

    # Exclude known non-process values
    if _is_protocol_value(val):
        return False
    if _is_action_value(val):
        return False
    if _is_address_value(val):
        return False
    if _is_date_value(val):
        return False
    if _is_time_value(val):
        return False

    # Match *.exe, System, Unknown, or similar process names
    return (
        val.endswith(".exe")
        or val.lower() in ["system", "unknown"]
        or (len(val) > 0 and ":" not in val and "," not in val)
    )


def _detect_column_type(values: List[str], verbose: bool = False) -> Optional[str]:
    """Detect column type based on its values.

    Detection order (from most to least specific):
    1. Protocol (TCP, UDP, etc.)
    2. Action (Added, Removed)
    3. Address (ip:port pattern)
    4. Date (date patterns)
    5. Time (time patterns)
    6. Process (everything else that's not empty)

    Args:
        values: List of values from the column
        verbose: Whether to print verbose logging messages

    Returns:
        Column type: 'Protocol', 'Action', 'LocalAddr', 'RemoteAddr',
                     'Date', 'Time', 'Process', or None
    """
    if not values:
        return None

    # Sample up to 20 non-empty values for detection
    sample_values = [v for v in values if v and v.strip()][:20]
    if not sample_values:
        return None

    # Count matches for each type
    protocol_matches = sum(1 for v in sample_values if _is_protocol_value(v))
    action_matches = sum(1 for v in sample_values if _is_action_value(v))
    address_matches = sum(1 for v in sample_values if _is_address_value(v))
    date_matches = sum(1 for v in sample_values if _is_date_value(v))
    time_matches = sum(1 for v in sample_values if _is_time_value(v))
    process_matches = sum(1 for v in sample_values if _is_process_value(v))

    total_samples = len(sample_values)
    threshold = 0.8  # 80% of values must match

    log_verbose(
        f"Column detection: protocol={protocol_matches}, action={action_matches}, "
        f"address={address_matches}, date={date_matches}, time={time_matches}, "
        f"process={process_matches} out of {total_samples}",
        verbose,
    )

    # Check in order of specificity
    if protocol_matches / total_samples >= threshold:
        return "Protocol"
    if action_matches / total_samples >= threshold:
        return "Action"
    if address_matches / total_samples >= threshold:
        # Need to determine if it's LocalAddr or RemoteAddr
        # This will be resolved when we have two address columns
        return "Address"
    if date_matches / total_samples >= threshold:
        return "Date"
    if time_matches / total_samples >= threshold:
        return "Time"
    if process_matches / total_samples >= threshold:
        return "Process"

    return None


def _auto_detect_headers(
    rows: List[List[str]], headers: Optional[List[str]], verbose: bool = False
) -> Dict[str, int]:
    """Auto-detect column headers based on content.

    Args:
        rows: List of data rows (without header)
        headers: Optional existing headers from CSV
        verbose: Whether to print verbose logging messages

    Returns:
        Dictionary mapping standard header names to column indices

    Raises:
        ValueError: If columns are too ambiguous to detect
    """
    if not rows:
        raise ValueError("No data rows to analyze for column detection")

    num_cols = len(rows[0])
    log_verbose(f"Auto-detecting columns for {num_cols} columns", verbose)

    # Transpose rows to get columns
    columns = []
    for col_idx in range(num_cols):
        col_values = [row[col_idx] if col_idx < len(row) else "" for row in rows]
        columns.append(col_values)

    # Detect each column type
    detected_types = []
    for col_idx, col_values in enumerate(columns):
        header_name = headers[col_idx] if headers and col_idx < len(headers) else None
        col_type = _detect_column_type(col_values, verbose)
        detected_types.append((col_idx, header_name, col_type))
        log_verbose(
            f"Column {col_idx} (header: '{header_name}'): detected as '{col_type}'",
            verbose,
        )

    # Build mapping from standard names to column indices
    mapping: Dict[str, int] = {}
    used_indices: Set[int] = set()
    address_indices: List[int] = []

    # First pass: map specific types
    for col_idx, header_name, col_type in detected_types:
        if col_type == "Protocol":
            mapping["Protocol"] = col_idx
            used_indices.add(col_idx)
        elif col_type == "Action":
            mapping["Action"] = col_idx
            used_indices.add(col_idx)
        elif col_type == "Date":
            mapping["Date"] = col_idx
            used_indices.add(col_idx)
        elif col_type == "Time":
            mapping["Time"] = col_idx
            used_indices.add(col_idx)
        elif col_type == "Process":
            mapping["Process"] = col_idx
            used_indices.add(col_idx)
        elif col_type == "Address":
            address_indices.append(col_idx)

    # Handle address columns (need two: LocalAddr and RemoteAddr)
    if len(address_indices) >= 2:
        # Assign in order: first is LocalAddr, second is RemoteAddr
        mapping["LocalAddr"] = address_indices[0]
        mapping["RemoteAddr"] = address_indices[1]
        used_indices.add(address_indices[0])
        used_indices.add(address_indices[1])
        log_verbose(
            f"Assigned LocalAddr to column {address_indices[0]}, "
            f"RemoteAddr to column {address_indices[1]}",
            verbose,
        )
    elif len(address_indices) == 1:
        log_verbose("Warning: Only found one address column, expected two", verbose)

    # Check for required columns
    required = ["Action", "Protocol", "LocalAddr", "RemoteAddr"]
    missing = [col for col in required if col not in mapping]
    if missing:
        log_verbose(f"Missing required columns: {missing}", verbose)
        # Try to use header names if available
        if headers:
            for col_idx, header in enumerate(headers):
                if not header:
                    continue
                header_clean = header.strip()
                if header_clean in required and header_clean not in mapping:
                    mapping[header_clean] = col_idx
                    used_indices.add(col_idx)
                    log_verbose(
                        f"Using header name for {header_clean} at column {col_idx}",
                        verbose,
                    )

    # Re-check missing columns
    missing = [col for col in required if col not in mapping]
    if missing:
        raise ValueError(
            f"Unable to auto-detect required columns: {missing}. "
            f"Data is too ambiguous. Please provide proper headers."
        )

    log_verbose(f"Final column mapping: {mapping}", verbose)
    return mapping


def parse_log_timestamp(
    date_str: str, time_str: str, default_date: str = "01/01/1970"
) -> Optional[datetime]:
    """Parse log timestamp from date and time strings.

    Args:
        date_str: Date in DD/MM/YYYY or other formats (can be empty)
        time_str: Time in HH.MM.SS, HH:MM:SS or other formats
        default_date: Default date to use if date_str is empty

    Returns:
        Datetime object or None if parsing fails
    """
    if not time_str or not time_str.strip():
        return None

    # Use default date if date_str is missing
    if not date_str or not date_str.strip():
        date_str = default_date

    date_str = date_str.strip()
    time_str = time_str.strip()

    # Normalize time string (replace . or - with :)
    time_normalized = time_str.replace(".", ":").replace("-", ":")

    # Try various date formats in order of preference
    # Note: DD/MM/YYYY vs MM/DD/YYYY is ambiguous for dates like 01/02/2025.
    # We try DD/MM/YYYY first as it's more common internationally.
    # For unambiguous dates (e.g., 25/01/2025), only DD/MM/YYYY will succeed.
    date_formats = [
        "%d/%m/%Y",  # DD/MM/YYYY (preferred for slash-separated)
        "%m/%d/%Y",  # MM/DD/YYYY (fallback for slash-separated)
        "%Y-%m-%d",  # YYYY-MM-DD (ISO format, unambiguous)
        "%d-%m-%Y",  # DD-MM-YYYY (European format)
        "%m-%d-%Y",  # MM-DD-YYYY (US format)
        "%d.%m.%Y",  # DD.MM.YYYY (European format)
    ]

    for date_format in date_formats:
        try:
            datetime_str = f"{date_str} {time_normalized}"
            return datetime.strptime(datetime_str, f"{date_format} %H:%M:%S")
        except ValueError:
            # Try with microseconds
            try:
                return datetime.strptime(datetime_str, f"{date_format} %H:%M:%S.%f")
            except ValueError:
                continue

    # Try Unix timestamp (if time_str looks like a number)
    try:
        timestamp = float(time_str)
        return datetime.fromtimestamp(timestamp)
    except (ValueError, OSError):
        pass

    return None


def extract_connection_id(local_addr: str, remote_addr: str) -> str:
    """Extract connection identifier from local and remote addresses.

    Args:
        local_addr: Local address in format ip:port
        remote_addr: Remote address in format ip:port

    Returns:
        Connection identifier as "local_ip:local_port,remote_ip:remote_port"
    """
    return f"{local_addr.strip()},{remote_addr.strip()}"


def parse_log_csv(csv_content: str, verbose: bool = False) -> List[Dict[str, str]]:
    """Parse log CSV content into list of log entries.

    Supports:
    - Headers in any order
    - Missing headers (auto-detects based on content)
    - Various date/time formats

    Args:
        csv_content: CSV content with log entries
        verbose: Whether to print verbose logging messages

    Returns:
        List of dictionaries containing log entry data with standardized keys:
        Date, Time, Action, Process, Protocol, LocalAddr, RemoteAddr

    Raises:
        ValueError: If CSV format is invalid or too ambiguous
    """
    content = csv_content.strip()
    if not content:
        raise ValueError("CSV content is empty")

    lines = content.splitlines()

    # Try to parse with csv.reader first to get all rows
    reader_list = list(csv.reader(lines))
    if not reader_list:
        raise ValueError("CSV content is empty")

    # First row might be headers or data
    first_row = reader_list[0]
    data_rows = reader_list[1:] if len(reader_list) > 1 else []

    # Check if first row looks like headers
    has_headers = False
    headers = None

    # Common header names we expect
    expected_headers = {
        "Date",
        "Time",
        "Action",
        "Process",
        "Protocol",
        "LocalAddr",
        "RemoteAddr",
    }

    # If any value in first row matches expected headers, treat it as headers
    if any(val.strip() in expected_headers for val in first_row if val):
        has_headers = True
        headers = [h.strip() if h else h for h in first_row]
        log_verbose(f"Detected headers in first row: {headers}", verbose)
    else:
        # First row is data
        log_verbose("No headers detected, will auto-detect columns", verbose)
        data_rows = reader_list

    # Check if we have standard headers (all expected columns present)
    standard_headers = False
    if has_headers and headers:
        header_set = {h for h in headers if h}
        required_subset = {"Action", "Protocol", "LocalAddr", "RemoteAddr"}
        if required_subset.issubset(header_set):
            standard_headers = True
            log_verbose("Standard headers detected, using them directly", verbose)

    # Auto-detect columns if needed
    column_mapping = None
    if not standard_headers:
        log_verbose("Attempting auto-detection of columns", verbose)
        try:
            column_mapping = _auto_detect_headers(data_rows, headers, verbose)
        except ValueError as e:
            # If auto-detection fails and we have headers, try to use them
            if has_headers and headers:
                log_verbose(
                    f"Auto-detection failed: {e}. Trying to use provided headers.",
                    verbose,
                )
                # Build a simple mapping from header names
                column_mapping = {}
                for idx, header in enumerate(headers):
                    if header and header in expected_headers:
                        column_mapping[header] = idx

                # Check if we have required columns
                required = ["Action", "Protocol", "LocalAddr", "RemoteAddr"]
                missing = [col for col in required if col not in column_mapping]
                if missing:
                    raise ValueError(
                        f"Missing required columns: {missing}. "
                        f"Available headers: {headers}"
                    )
            else:
                raise

    # Parse log entries
    log_entries = []

    if standard_headers:
        # Use DictReader with standard headers
        reader = csv.DictReader(lines)
        if reader.fieldnames:
            reader.fieldnames = [
                name.strip() if name is not None else name for name in reader.fieldnames
            ]
            log_verbose(f"Log CSV headers: {reader.fieldnames}", verbose)

        for row in reader:
            # Skip empty rows
            if any(value and value.strip() for value in row.values()):
                normalized_row = {
                    key.strip(): value for key, value in row.items() if key is not None
                }
                log_entries.append(normalized_row)
    else:
        # Use column mapping
        if column_mapping is None:
            raise ValueError(
                "Column mapping is not available. Cannot parse log entries."
            )
        log_verbose(f"Using column mapping: {column_mapping}", verbose)

        for row_data in data_rows:
            if not any(value and value.strip() for value in row_data):
                continue  # Skip empty rows

            # Build standardized row
            entry = {}
            for std_name, col_idx in column_mapping.items():
                if col_idx < len(row_data):
                    entry[std_name] = row_data[col_idx]
                else:
                    entry[std_name] = ""

            log_entries.append(entry)

    log_verbose(f"Parsed {len(log_entries)} log entries from CSV", verbose)
    return log_entries


def match_connection_events(
    log_entries: List[Dict[str, str]], verbose: bool = False
) -> List[Dict[str, str]]:
    """Match Added and Removed events for connections.

    Each connection is identified by local_ip:local_port,remote_ip:remote_port.
    Expected order for one connection entry:
    - Added processName.exe
    - Added Unknown
    - Removed processName.exe
    - Removed Unknown

    Connection identifiers may be reused after removal, so we detect connection
    boundaries by tracking when we transition from Removed events back to Added
    events for the same connection identifier.

    Incomplete connections (due to log cutoff) are handled:
    - Removed events without matching Added events (connection started before
      logging)
    - Added events without matching Removed events (connection ongoing at log
      end)

    Args:
        log_entries: List of log entry dictionaries
        verbose: Whether to print verbose logging messages

    Returns:
        List of matched connection dictionaries with start/end timestamps
    """
    log_verbose(
        f"Matching connection events from {len(log_entries)} log entries", verbose
    )

    # Process events in order and detect connection boundaries
    result = []
    # Track active connections: conn_id -> {added_events, removed_events}
    active_connections: Dict[str, Dict[str, List[Dict[str, str]]]] = {}

    for entry in log_entries:
        # Extract connection identifier
        local_addr = entry.get("LocalAddr", "")
        remote_addr = entry.get("RemoteAddr", "")
        conn_id = extract_connection_id(local_addr, remote_addr)
        action = entry.get("Action", "").strip()

        if not local_addr or not remote_addr:
            log_verbose(
                f"Skipping entry with missing address fields: "
                f"LocalAddr='{local_addr}', RemoteAddr='{remote_addr}'",
                verbose,
            )
            continue

        # Initialize connection if not seen before
        if conn_id not in active_connections:
            active_connections[conn_id] = {
                "added_events": [],
                "removed_events": [],
            }

        conn = active_connections[conn_id]

        # Detect connection reuse: if we see an Added event and we already
        # have Removed events, this is a new connection
        if action == "Added" and conn["removed_events"]:
            # Complete the previous connection
            completed_conn = _create_connection_entry(
                conn_id, conn["added_events"], conn["removed_events"], verbose
            )
            if completed_conn:
                result.append(completed_conn)
                log_verbose(
                    f"Completed connection (reuse detected): {completed_conn['Name']}",
                    verbose,
                )

            # Start a new connection
            active_connections[conn_id] = {
                "added_events": [entry],
                "removed_events": [],
            }
        elif action == "Added":
            conn["added_events"].append(entry)
        elif action == "Removed":
            conn["removed_events"].append(entry)

    # Process remaining active connections
    log_verbose(
        f"Processing {len(active_connections)} remaining active connections", verbose
    )
    for conn_id, conn in active_connections.items():
        completed_conn = _create_connection_entry(
            conn_id, conn["added_events"], conn["removed_events"], verbose
        )
        if completed_conn:
            result.append(completed_conn)
            log_verbose(f"Completed connection: {completed_conn['Name']}", verbose)

    log_verbose(f"Matched {len(result)} total connections", verbose)
    return result


def _create_connection_entry(
    conn_id: str,
    added_events: List[Dict[str, str]],
    removed_events: List[Dict[str, str]],
    verbose: bool = False,
) -> Optional[Dict[str, str]]:
    """Create a connection entry from Added and Removed events.

    Args:
        conn_id: Connection identifier
        added_events: List of Added events for this connection
        removed_events: List of Removed events for this connection
        verbose: Whether to print verbose logging messages

    Returns:
        Dictionary with Name, start_timestamp, end_timestamp or None if no
        valid timestamps
    """
    # Get timestamps
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    process_name = "Unknown"

    # Find earliest Added event for start time
    if added_events:
        for event in added_events:
            dt = parse_log_timestamp(event.get("Date", ""), event.get("Time", ""))
            if dt:
                if start_time is None or dt < start_time:
                    start_time = dt
                # Prefer non-Unknown process names
                proc = event.get("Process", "Unknown").strip()
                if proc and proc != "Unknown":
                    process_name = proc

    # Find latest Removed event for end time
    if removed_events:
        for event in removed_events:
            dt = parse_log_timestamp(event.get("Date", ""), event.get("Time", ""))
            if dt:
                if end_time is None or dt > end_time:
                    end_time = dt
                # Prefer non-Unknown process names if we don't have one yet
                if process_name == "Unknown":
                    proc = event.get("Process", "Unknown").strip()
                    if proc and proc != "Unknown":
                        process_name = proc

    # Handle incomplete connections
    # If we have Added but no Removed (connection ongoing at log end)
    if start_time and not end_time:
        # Use the latest Added event timestamp as end time
        end_time = start_time

    # If we have Removed but no Added (connection started before logging)
    if end_time and not start_time:
        # Find the earliest Removed event for start time
        for event in removed_events:
            dt = parse_log_timestamp(event.get("Date", ""), event.get("Time", ""))
            if dt:
                if start_time is None or dt < start_time:
                    start_time = dt
        # If still no start_time, use end_time
        if not start_time:
            start_time = end_time

    # Only include connections with at least one timestamp
    if not (start_time or end_time):
        return None

    # Ensure both timestamps exist
    if not start_time:
        start_time = end_time
    if not end_time:
        end_time = start_time

    # Type narrowing: at this point, both are not None
    assert start_time is not None
    assert end_time is not None

    # Get protocol and addresses for the task name
    protocol = ""
    if added_events:
        protocol = added_events[0].get("Protocol", "TCP")
    elif removed_events:
        protocol = removed_events[0].get("Protocol", "TCP")

    local_addr = conn_id.split(",")[0] if "," in conn_id else ""
    remote_addr = conn_id.split(",")[1] if "," in conn_id else ""

    # Create task name combining process, protocol, and connection info
    task_name = f"{process_name} ({protocol}): {local_addr} -> {remote_addr}"

    return {
        "Name": task_name,
        "start_timestamp": start_time.strftime("%Y-%m-%d %H:%M:%S"),
        "end_timestamp": end_time.strftime("%Y-%m-%d %H:%M:%S"),
    }


def convert_log_to_csv(log_content: str, verbose: bool = False) -> str:
    """Convert log format to standard CSV format for diagram visualization.

    Args:
        log_content: Log CSV content with Date,Time,Action,Process,Protocol,
                     LocalAddr,RemoteAddr
        verbose: Whether to print verbose logging messages

    Returns:
        Standard CSV format with Name,start_timestamp,end_timestamp

    Raises:
        ValueError: If log format is invalid
    """
    log_entries = parse_log_csv(log_content, verbose)
    matched_connections = match_connection_events(log_entries, verbose)

    # Convert to CSV format
    lines = ["Name,start_timestamp,end_timestamp"]
    for conn in matched_connections:
        name = conn["Name"]
        start = conn["start_timestamp"]
        end = conn["end_timestamp"]
        lines.append(f'"{name}",{start},{end}')

    return "\n".join(lines)
