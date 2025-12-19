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
import sys
from datetime import datetime
from typing import List, Dict, Optional


def log_verbose(message: str, verbose: bool = False) -> None:
    """Print verbose logging message if verbose mode is enabled.

    Args:
        message: Message to print
        verbose: Whether to print the message
    """
    if verbose:
        print(f"[DEBUG] {message}", file=sys.stderr)


def parse_log_timestamp(date_str: str, time_str: str) -> Optional[datetime]:
    """Parse log timestamp from date and time strings.

    Args:
        date_str: Date in DD/MM/YYYY format
        time_str: Time in HH.MM.SS format

    Returns:
        Datetime object or None if parsing fails
    """
    if not date_str or not time_str:
        return None

    try:
        # Combine date and time, replacing . with : in time
        datetime_str = f"{date_str.strip()} {time_str.strip().replace('.', ':')}"
        return datetime.strptime(datetime_str, "%d/%m/%Y %H:%M:%S")
    except (ValueError, AttributeError):
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

    Args:
        csv_content: CSV content with log entries
        verbose: Whether to print verbose logging messages

    Returns:
        List of dictionaries containing log entry data

    Raises:
        ValueError: If CSV format is invalid
    """
    content = csv_content.strip()
    if not content:
        raise ValueError("CSV content is empty")

    lines = content.splitlines()
    reader = csv.DictReader(lines)

    # Normalize field names by stripping whitespace
    if reader.fieldnames:
        original_fieldnames = list(reader.fieldnames)
        reader.fieldnames = [name.strip() if name else name for name in reader.fieldnames]
        log_verbose(f"Log CSV headers: {reader.fieldnames}", verbose)
        if original_fieldnames != list(reader.fieldnames):
            log_verbose(f"Normalized headers (removed whitespace): {original_fieldnames} -> {reader.fieldnames}", verbose)

    log_entries = []
    for row in reader:
        # Skip empty rows
        if any(value and value.strip() for value in row.values()):
            # Normalize keys in the row dictionary to match normalized fieldnames
            normalized_row = {key.strip() if key else key: value for key, value in row.items()}
            log_entries.append(normalized_row)

    log_verbose(f"Parsed {len(log_entries)} log entries from CSV", verbose)
    return log_entries


def match_connection_events(log_entries: List[Dict[str, str]], verbose: bool = False) -> List[Dict[str, str]]:
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
    log_verbose(f"Matching connection events from {len(log_entries)} log entries", verbose)
    
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
            log_verbose(f"Skipping entry with missing address fields: LocalAddr='{local_addr}', RemoteAddr='{remote_addr}'", verbose)
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
                log_verbose(f"Completed connection (reuse detected): {completed_conn['Name']}", verbose)

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
    log_verbose(f"Processing {len(active_connections)} remaining active connections", verbose)
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
