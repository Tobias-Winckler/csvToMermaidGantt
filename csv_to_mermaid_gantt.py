"""CSV to Mermaid Gantt Chart Converter.

This module provides functionality to convert CSV files to Mermaid Gantt chart format.
Expected CSV format:
- task_name,start_date,duration,status
- Or: task_name,start_date,end_date,status
"""

import argparse
import csv
import sys
from typing import List, Dict


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
        # Filter out empty rows where all values are empty strings
        if any(value.strip() for value in row.values()):
            tasks.append(dict(row))

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

        # Add dates
        if "start_date" in task and task["start_date"].strip():
            task_line += f", {task['start_date'].strip()}"

            if "duration" in task and task["duration"].strip():
                task_line += f", {task['duration'].strip()}"
            elif "end_date" in task and task["end_date"].strip():
                task_line += f", {task['end_date'].strip()}"

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
