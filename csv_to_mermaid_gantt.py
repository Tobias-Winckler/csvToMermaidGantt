"""CSV to Mermaid Gantt Chart Converter.

This module provides functionality to convert CSV files to Mermaid Gantt chart format.
Supports multiple CSV formats:
- Digital forensics format: Name,start_timestamp,end_timestamp
- Legacy format: task_name,start_date,duration,status
- Legacy format: task_name,start_date,end_date,status

Timestamps can be in ISO 8601 format or Unix timestamps (seconds since epoch).
"""

import argparse
import csv
import sys
from datetime import datetime
from typing import List, Dict, Optional


def parse_timestamp(timestamp_str: str) -> Optional[datetime]:
    """Parse a timestamp string into a datetime object.

    Args:
        timestamp_str: Timestamp in ISO 8601 format or Unix timestamp

    Returns:
        Datetime object or None if parsing fails
    """
    if not timestamp_str or not timestamp_str.strip():
        return None

    timestamp_str = timestamp_str.strip()

    # Try Unix timestamp (seconds since epoch)
    try:
        timestamp_float = float(timestamp_str)
        return datetime.fromtimestamp(timestamp_float)
    except (ValueError, OSError):
        pass

    # Try various ISO 8601 formats
    iso_formats = [
        "%Y-%m-%dT%H:%M:%S.%fZ",  # 2024-01-01T12:30:45.123456Z
        "%Y-%m-%dT%H:%M:%SZ",  # 2024-01-01T12:30:45Z
        "%Y-%m-%dT%H:%M:%S.%f",  # 2024-01-01T12:30:45.123456
        "%Y-%m-%dT%H:%M:%S",  # 2024-01-01T12:30:45
        "%Y-%m-%d %H:%M:%S.%f",  # 2024-01-01 12:30:45.123456
        "%Y-%m-%d %H:%M:%S",  # 2024-01-01 12:30:45
        "%Y-%m-%d",  # 2024-01-01
    ]

    for fmt in iso_formats:
        try:
            return datetime.strptime(timestamp_str, fmt)
        except ValueError:
            continue

    return None


def normalize_task_dict(task: Dict[str, str]) -> Dict[str, str]:
    """Normalize task dictionary to use consistent field names.

    Converts 'Name' to 'task_name' and timestamp fields to date fields.

    Args:
        task: Task dictionary with potentially varied field names

    Returns:
        Normalized task dictionary
    """
    normalized = dict(task)

    # Convert 'Name' to 'task_name' for consistency
    if "Name" in normalized and "task_name" not in normalized:
        normalized["task_name"] = normalized["Name"]

    # Handle timestamp-based format (Name,start_timestamp,end_timestamp)
    if "start_timestamp" in normalized:
        start_dt = parse_timestamp(normalized["start_timestamp"])
        if start_dt:
            # Use second precision for digital forensics
            normalized["start_date"] = start_dt.strftime("%Y-%m-%d")
            normalized["start_time"] = start_dt.strftime("%H:%M:%S")

    if "end_timestamp" in normalized:
        end_dt = parse_timestamp(normalized["end_timestamp"])
        if end_dt:
            normalized["end_date"] = end_dt.strftime("%Y-%m-%d")
            normalized["end_time"] = end_dt.strftime("%H:%M:%S")

    return normalized


def parse_csv(csv_content: str) -> List[Dict[str, str]]:
    """Parse CSV content and return a list of task dictionaries.

    Args:
        csv_content: CSV formatted string with task data

    Returns:
        List of dictionaries containing task information

    Raises:
        ValueError: If CSV format is invalid
    """
    content = csv_content.strip()
    if not content:
        raise ValueError("CSV content is empty")

    lines = content.split("\n")
    reader = csv.DictReader(lines)
    tasks = []

    for row in reader:
        # Filter out empty rows where all values are empty strings or None
        if any(value and value.strip() for value in row.values()):
            normalized_task = normalize_task_dict(dict(row))
            tasks.append(normalized_task)

    return tasks


def validate_task(task: Dict[str, str]) -> None:
    """Validate that a task has required fields.

    Args:
        task: Dictionary containing task data

    Raises:
        ValueError: If required fields are missing
    """
    required_fields = ["task_name"]
    for field in required_fields:
        if field not in task or not task[field].strip():
            raise ValueError(f"Missing required field: {field}")


def format_task_id(task_name: str) -> str:
    """Format task name as a valid Mermaid task ID.

    Args:
        task_name: Original task name

    Returns:
        Formatted task ID (lowercase, underscores for spaces)
    """
    return task_name.lower().replace(" ", "_").replace("-", "_")


def generate_mermaid_gantt(
    tasks: List[Dict[str, str]], title: str = "Gantt Chart"
) -> str:
    """Generate Mermaid Gantt chart from task data.

    Args:
        tasks: List of task dictionaries
        title: Title for the Gantt chart

    Returns:
        Mermaid Gantt chart as a string

    Raises:
        ValueError: If tasks list is empty or task data is invalid
    """
    if not tasks:
        raise ValueError("No tasks provided")

    # Determine if we need time precision based on whether start_time or end_time exist
    has_time = any("start_time" in task or "end_time" in task for task in tasks)

    if has_time:
        lines = ["gantt", f"    title {title}", "    dateFormat YYYY-MM-DD HH:mm:ss"]
    else:
        lines = ["gantt", f"    title {title}", "    dateFormat YYYY-MM-DD"]

    for task in tasks:
        validate_task(task)

        task_name = task["task_name"]
        task_id = format_task_id(task_name)

        # Build task line
        task_line = f"    {task_name} :{task_id}"

        # Add status if provided
        if "status" in task and task["status"].strip():
            status = task["status"].strip().lower()
            if status in ["active", "done", "crit"]:
                task_line += f", {status}"

        # Add dates with optional time component
        if "start_date" in task and task["start_date"].strip():
            start_date = task["start_date"].strip()
            if has_time and "start_time" in task and task["start_time"].strip():
                start_date = f"{start_date} {task['start_time'].strip()}"
            task_line += f", {start_date}"

            if "end_date" in task and task["end_date"].strip():
                end_date = task["end_date"].strip()
                if has_time and "end_time" in task and task["end_time"].strip():
                    end_date = f"{end_date} {task['end_time'].strip()}"
                task_line += f", {end_date}"
            elif "duration" in task and task["duration"].strip():
                task_line += f", {task['duration'].strip()}"

        lines.append(task_line)

    return "\n".join(lines)


def convert_csv_to_mermaid(csv_content: str, title: str = "Gantt Chart") -> str:
    """Convert CSV content to Mermaid Gantt chart.

    Args:
        csv_content: CSV formatted string with task data
        title: Title for the Gantt chart

    Returns:
        Mermaid Gantt chart as a string

    Raises:
        ValueError: If CSV format is invalid or task data is invalid
    """
    tasks = parse_csv(csv_content)
    return generate_mermaid_gantt(tasks, title)


def main() -> None:
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Convert CSV files to Mermaid Gantt charts"
    )
    parser.add_argument(
        "input_file",
        nargs="?",
        help="Input CSV file (if not provided, reads from stdin)",
    )
    parser.add_argument(
        "-o", "--output", help="Output file (if not provided, writes to stdout)"
    )
    parser.add_argument(
        "-t",
        "--title",
        default="Gantt Chart",
        help='Title for the Gantt chart (default: "Gantt Chart")',
    )

    args = parser.parse_args()

    try:
        # Read input
        if args.input_file:
            with open(args.input_file, "r", encoding="utf-8") as f:
                csv_content = f.read()
        else:
            csv_content = sys.stdin.read()

        # Convert
        mermaid_output = convert_csv_to_mermaid(csv_content, args.title)

        # Write output
        if args.output:
            with open(args.output, "w", encoding="utf-8") as f:
                f.write(mermaid_output)
        else:
            print(mermaid_output)

    except FileNotFoundError as e:
        print(f"Error: File not found - {e}", file=sys.stderr)
        sys.exit(1)
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Unexpected error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
