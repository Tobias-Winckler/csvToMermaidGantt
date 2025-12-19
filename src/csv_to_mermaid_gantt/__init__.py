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


def log_verbose(message: str, verbose: bool = False) -> None:
    """Print verbose logging message if verbose mode is enabled.

    Args:
        message: Message to print
        verbose: Whether to print the message
    """
    if verbose:
        print(f"[DEBUG] {message}", file=sys.stderr)


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


def normalize_task_dict(task: Dict[str, str], verbose: bool = False) -> Dict[str, str]:
    """Normalize task dictionary to use consistent field names.

    Converts 'Name' to 'task_name' and timestamp fields to date fields.

    Args:
        task: Task dictionary with potentially varied field names
        verbose: Whether to print verbose logging messages

    Returns:
        Normalized task dictionary
    """
    normalized = dict(task)
    log_verbose(f"Normalizing task with fields: {list(task.keys())}", verbose)

    # Convert 'Name' to 'task_name' for consistency
    if "Name" in normalized and "task_name" not in normalized:
        normalized["task_name"] = normalized["Name"]
        log_verbose(
            f"Converted 'Name' field to 'task_name': {normalized['task_name']}", verbose
        )

    # Handle timestamp-based format (Name,start_timestamp,end_timestamp)
    if "start_timestamp" in normalized:
        start_dt = parse_timestamp(normalized["start_timestamp"])
        if start_dt:
            # Use second precision for digital forensics
            normalized["start_date"] = start_dt.strftime("%Y-%m-%d")
            normalized["start_time"] = start_dt.strftime("%H:%M:%S")
            log_verbose(
                f"Parsed start_timestamp: "
                f"{normalized['start_date']} {normalized['start_time']}",
                verbose,
            )

    if "end_timestamp" in normalized:
        end_dt = parse_timestamp(normalized["end_timestamp"])
        if end_dt:
            normalized["end_date"] = end_dt.strftime("%Y-%m-%d")
            normalized["end_time"] = end_dt.strftime("%H:%M:%S")
            log_verbose(
                f"Parsed end_timestamp: "
                f"{normalized['end_date']} {normalized['end_time']}",
                verbose,
            )

    return normalized


def parse_csv(csv_content: str, verbose: bool = False) -> List[Dict[str, str]]:
    """Parse CSV content and return a list of task dictionaries.

    Args:
        csv_content: CSV formatted string with task data
        verbose: Whether to print verbose logging messages

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

    log_verbose(f"CSV headers detected: {reader.fieldnames}", verbose)

    for idx, row in enumerate(reader):
        log_verbose(f"Processing row {idx + 1}: {dict(row)}", verbose)
        # Filter out empty rows where all values are empty strings or None
        if any(value and value.strip() for value in row.values()):
            normalized_task = normalize_task_dict(dict(row), verbose)
            tasks.append(normalized_task)
        else:
            log_verbose(f"Skipping empty row {idx + 1}", verbose)

    log_verbose(f"Parsed {len(tasks)} task(s) from CSV", verbose)
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
            # Filter out None keys which can occur when CSV rows have more
            # values than headers (malformed CSV with extra columns)
            available_fields = [k for k in task.keys() if k is not None]
            raise ValueError(
                f"Missing required field: '{field}'\n"
                f"Available fields in CSV: {available_fields}\n"
                f"Hint: Use 'Name' or 'task_name' as the header "
                f"for the task name column.\n"
                f"      Run with --verbose to see detailed parsing "
                f"information."
            )


def format_task_id(task_name: str) -> str:
    """Format task name as a valid Mermaid task ID.

    Args:
        task_name: Original task name

    Returns:
        Formatted task ID (lowercase, underscores for spaces)
    """
    return task_name.lower().replace(" ", "_").replace("-", "_")


def combine_tasks_by_name(
    tasks: List[Dict[str, str]],
    threshold_seconds: int = 60,
    verbose: bool = False,
) -> List[Dict[str, str]]:
    """Combine tasks with equal names if the gap between them is within threshold.

    Args:
        tasks: List of task dictionaries
        threshold_seconds: Maximum gap in seconds between tasks to combine them
        verbose: Whether to print verbose logging messages

    Returns:
        List of tasks with same-name tasks combined where appropriate
    """
    if not tasks:
        return tasks

    # Group tasks by name
    tasks_by_name: Dict[str, List[Dict[str, str]]] = {}
    for task in tasks:
        name = task.get("task_name", "")
        if name not in tasks_by_name:
            tasks_by_name[name] = []
        tasks_by_name[name].append(task)

    combined_tasks = []

    for task_name, task_list in tasks_by_name.items():
        # If only one task with this name, no combining needed
        if len(task_list) == 1:
            combined_tasks.extend(task_list)
            continue

        # Sort tasks by start time for this name
        # Only combine tasks that have both start and end timestamps
        combinable_tasks = []
        non_combinable_tasks = []

        for task in task_list:
            if (
                "start_date" in task
                and "end_date" in task
                and task["start_date"]
                and task["end_date"]
            ):
                # Parse datetime for sorting
                start_str = task["start_date"]
                if "start_time" in task and task.get("start_time"):
                    start_str = f"{start_str} {task['start_time']}"
                start_dt = parse_timestamp(start_str)

                end_str = task["end_date"]
                if "end_time" in task and task.get("end_time"):
                    end_str = f"{end_str} {task['end_time']}"
                end_dt = parse_timestamp(end_str)

                if start_dt and end_dt:
                    combinable_tasks.append((start_dt, end_dt, task))
                else:
                    non_combinable_tasks.append(task)
            else:
                non_combinable_tasks.append(task)

        # Sort combinable tasks by start time
        combinable_tasks.sort(key=lambda x: x[0])

        # Combine tasks within threshold
        if combinable_tasks:
            merged = []
            current_start, current_end, current_task = combinable_tasks[0]

            for i in range(1, len(combinable_tasks)):
                next_start, next_end, next_task = combinable_tasks[i]
                gap = (next_start - current_end).total_seconds()

                if gap <= threshold_seconds:
                    # Combine: extend current_end to next_end
                    log_verbose(
                        f"Combining '{task_name}': "
                        f"gap of {gap:.1f}s <= {threshold_seconds}s threshold",
                        verbose,
                    )
                    current_end = max(current_end, next_end)
                else:
                    # Gap too large, save current combined task and start new sequence
                    # Update the start and end date/time in the task dict
                    updated_task = dict(current_task)
                    updated_task["start_date"] = current_start.strftime("%Y-%m-%d")
                    if "start_time" in current_task:
                        updated_task["start_time"] = current_start.strftime("%H:%M:%S")
                    updated_task["end_date"] = current_end.strftime("%Y-%m-%d")
                    if "end_time" in current_task:
                        updated_task["end_time"] = current_end.strftime("%H:%M:%S")
                    merged.append(updated_task)

                    # Start new sequence with next task
                    current_start = next_start
                    current_end = next_end
                    current_task = next_task

            # Add the last combined task
            updated_task = dict(current_task)
            updated_task["start_date"] = current_start.strftime("%Y-%m-%d")
            if "start_time" in current_task:
                updated_task["start_time"] = current_start.strftime("%H:%M:%S")
            updated_task["end_date"] = current_end.strftime("%Y-%m-%d")
            if "end_time" in current_task:
                updated_task["end_time"] = current_end.strftime("%H:%M:%S")
            merged.append(updated_task)

            combined_tasks.extend(merged)

        # Add non-combinable tasks as-is
        combined_tasks.extend(non_combinable_tasks)

    return combined_tasks


def generate_mermaid_gantt(
    tasks: List[Dict[str, str]], title: str = "Gantt Chart", width: Optional[int] = None
) -> str:
    """Generate Mermaid Gantt chart from task data.

    Args:
        tasks: List of task dictionaries
        title: Title for the Gantt chart
        width: Optional width in pixels for the diagram (helps with narrow diagrams)
               Must be between 100 and 10000 pixels

    Returns:
        Mermaid Gantt chart as a string

    Raises:
        ValueError: If tasks list is empty or task data is invalid,
                    or if width is out of valid range
    """
    if not tasks:
        raise ValueError("No tasks provided")

    # Validate width parameter
    if width is not None:
        if not isinstance(width, int) or width < 100 or width > 10000:
            raise ValueError("Width must be an integer between 100 and 10000 pixels")

    # Determine if we need time precision based on whether start_time or end_time exist
    has_time = any("start_time" in task or "end_time" in task for task in tasks)

    # Add configuration directive if width is specified
    lines = []
    if width is not None:
        # Configure Mermaid to set diagram width and font size for better layout
        # This helps with rendering when exporting to PNG/SVG
        config = (
            f"%%{{init: {{'theme':'default', "
            f"'themeVariables': {{'fontSize': '16px'}}, "
            f"'gantt': {{'useWidth': {width}}}}}}}%%"
        )
        lines.append(config)

    if has_time:
        lines.extend(
            ["gantt", f"    title {title}", "    dateFormat YYYY-MM-DD HH:mm:ss"]
        )
    else:
        lines.extend(["gantt", f"    title {title}", "    dateFormat YYYY-MM-DD"])

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


def convert_csv_to_mermaid(
    csv_content: str,
    title: str = "Gantt Chart",
    verbose: bool = False,
    width: Optional[int] = None,
    combine_threshold: Optional[int] = 60,
) -> str:
    """Convert CSV content to Mermaid Gantt chart.

    Args:
        csv_content: CSV formatted string with task data
        title: Title for the Gantt chart
        verbose: Whether to print verbose logging messages
        width: Optional width in pixels for the diagram (helps with narrow diagrams)
        combine_threshold: Optional threshold in seconds for combining tasks with
                          equal names (default: 60). Set to None to disable combining.

    Returns:
        Mermaid Gantt chart as a string

    Raises:
        ValueError: If CSV format is invalid or task data is invalid
    """
    tasks = parse_csv(csv_content, verbose)

    # Combine tasks with equal names if threshold is set
    if combine_threshold is not None:
        log_verbose(
            f"Combining tasks with threshold of {combine_threshold} seconds", verbose
        )
        tasks = combine_tasks_by_name(tasks, combine_threshold, verbose)

    return generate_mermaid_gantt(tasks, title, width)


def main() -> None:
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description=(
            "Convert CSV files to Mermaid Gantt charts or "
            "interactive HTML visualizations"
        )
    )
    parser.add_argument(
        "input_file",
        nargs="*",
        help=(
            "Input CSV file(s) (if not provided, reads from stdin). "
            "Multiple files can be specified for HTML output."
        ),
    )
    parser.add_argument(
        "-o", "--output", help="Output file (if not provided, writes to stdout)"
    )
    parser.add_argument(
        "-t",
        "--title",
        default="Gantt Chart",
        help='Title for the chart (default: "Gantt Chart")',
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Enable verbose output for debugging",
    )
    parser.add_argument(
        "-w",
        "--width",
        type=int,
        help=(
            "Diagram width in pixels "
            "(helps with narrow diagrams when there are many tasks)"
        ),
    )
    parser.add_argument(
        "-c",
        "--combine-threshold",
        type=int,
        default=60,
        help=(
            "Threshold in seconds for combining tasks with equal names "
            "(default: 60). Set to 0 to disable combining."
        ),
    )
    parser.add_argument(
        "--html",
        action="store_true",
        help=(
            "Generate interactive HTML with time-synced visualizations "
            "instead of Mermaid format"
        ),
    )
    parser.add_argument(
        "--no-timeline",
        action="store_true",
        help="Disable timeline chart in HTML output",
    )
    parser.add_argument(
        "--no-histogram",
        action="store_true",
        help="Disable histogram in HTML output",
    )
    parser.add_argument(
        "--no-line-graph",
        action="store_true",
        help="Disable line graph in HTML output",
    )

    args = parser.parse_args()
    verbose = args.verbose

    try:
        # Handle HTML output mode
        if args.html:
            from .html_visualizations import convert_csv_files_to_html

            csv_files = []

            # Read input files
            if args.input_file:
                log_verbose(f"Reading {len(args.input_file)} input file(s)", verbose)
                for input_path in args.input_file:
                    log_verbose(f"Reading input from file: {input_path}", verbose)
                    with open(input_path, "r", encoding="utf-8-sig") as f:
                        csv_content = f.read()
                    csv_files.append({"name": input_path, "content": csv_content})
            else:
                log_verbose("Reading input from stdin", verbose)
                csv_content = sys.stdin.read()
                csv_files.append({"name": "stdin", "content": csv_content})

            # Set threshold to None if 0 is specified (to disable combining)
            threshold = args.combine_threshold if args.combine_threshold > 0 else None

            # Generate HTML
            log_verbose("Generating HTML visualization", verbose)
            html_output = convert_csv_files_to_html(
                csv_files,
                title=args.title,
                show_timeline=not args.no_timeline,
                show_histogram=not args.no_histogram,
                show_line_graph=not args.no_line_graph,
                verbose=verbose,
                combine_threshold=threshold,
            )
            log_verbose("HTML generation successful", verbose)

            # Write output
            if args.output:
                log_verbose(f"Writing output to file: {args.output}", verbose)
                with open(args.output, "w", encoding="utf-8") as f:
                    f.write(html_output)
            else:
                print(html_output)

            return

        # Original Mermaid output mode
        # Read input
        if args.input_file:
            # For backward compatibility, take only the first file for Mermaid output
            input_path = (
                args.input_file[0]
                if isinstance(args.input_file, list)
                else args.input_file
            )
            log_verbose(f"Reading input from file: {input_path}", verbose)
            with open(input_path, "r", encoding="utf-8-sig") as f:
                csv_content = f.read()
        else:
            log_verbose("Reading input from stdin", verbose)
            csv_content = sys.stdin.read()

        log_verbose(
            f"Input CSV content: {len(csv_content)} bytes, "
            f"{len(csv_content.splitlines())} lines",
            verbose,
        )

        # Convert
        log_verbose("Starting CSV to Mermaid conversion", verbose)
        # Set threshold to None if 0 is specified (to disable combining)
        threshold = args.combine_threshold if args.combine_threshold > 0 else None
        mermaid_output = convert_csv_to_mermaid(
            csv_content, args.title, verbose, args.width, threshold
        )
        log_verbose("Conversion successful", verbose)

        # Write output
        if args.output:
            log_verbose(f"Writing output to file: {args.output}", verbose)
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
