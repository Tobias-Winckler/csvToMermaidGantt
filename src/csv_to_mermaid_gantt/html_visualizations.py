"""HTML Visualization Generator for Time-Synced Charts.

This module provides functionality to generate interactive HTML visualizations
with time-synchronized Timeline Charts (Gantt-like), Line Graphs, and Histograms.
Uses Plotly.js for interactive, zoomable charts with synchronized time axes.
"""

from typing import List, Dict, Optional, Any
from datetime import datetime
import json
from . import parse_csv, parse_timestamp


def prepare_timeline_data(tasks: List[Dict[str, str]]) -> List[Dict[str, Any]]:
    """Prepare task data for timeline (Gantt-like) visualization.

    Args:
        tasks: List of task dictionaries from CSV

    Returns:
        List of timeline data items with start, end, and task name
    """
    timeline_data = []

    for task in tasks:
        task_name = task.get("task_name", "Unknown")

        # Get start and end timestamps
        start_str = task.get("start_date", "")
        if "start_time" in task and task.get("start_time"):
            start_str = f"{start_str} {task['start_time']}"

        end_str = task.get("end_date", "")
        if "end_time" in task and task.get("end_time"):
            end_str = f"{end_str} {task['end_time']}"

        start_dt = parse_timestamp(start_str) if start_str else None
        end_dt = parse_timestamp(end_str) if end_str else None

        if start_dt and end_dt:
            timeline_data.append(
                {
                    "task": task_name,
                    "start": start_dt.isoformat(),
                    "end": end_dt.isoformat(),
                    "start_ts": start_dt.timestamp(),
                    "end_ts": end_dt.timestamp(),
                }
            )

    return timeline_data


def prepare_histogram_data(
    tasks: List[Dict[str, str]], bin_size_seconds: int = 3600
) -> Dict[str, List[Any]]:
    """Prepare histogram data showing event counts over time.

    Args:
        tasks: List of task dictionaries from CSV
        bin_size_seconds: Size of histogram bins in seconds (default: 3600 = 1 hour)

    Returns:
        Dictionary with histogram bins and counts
    """
    if not tasks:
        return {"bins": [], "counts": []}

    # Collect all start times
    start_times = []
    for task in tasks:
        start_str = task.get("start_date", "")
        if "start_time" in task and task.get("start_time"):
            start_str = f"{start_str} {task['start_time']}"

        start_dt = parse_timestamp(start_str) if start_str else None
        if start_dt:
            start_times.append(start_dt.timestamp())

    if not start_times:
        return {"bins": [], "counts": []}

    # Create bins
    min_time = min(start_times)
    max_time = max(start_times)

    bins: List[str] = []
    counts: List[int] = []

    current_bin = min_time
    while current_bin <= max_time:
        # Count events in this bin
        count = sum(
            1 for t in start_times if current_bin <= t < current_bin + bin_size_seconds
        )
        # Include bins with data or empty bins between data points
        has_data = count > 0
        previous_bin_has_data = bins and counts[-1] > 0
        if has_data or previous_bin_has_data:
            bins.append(datetime.fromtimestamp(current_bin).isoformat())
            counts.append(count)
        current_bin += bin_size_seconds

    return {"bins": bins, "counts": counts}


def prepare_line_graph_data(
    tasks: List[Dict[str, str]], value_field: str = "duration"
) -> Dict[str, List[Any]]:
    """Prepare line graph data from task values over time.

    Args:
        tasks: List of task dictionaries from CSV
        value_field: Field name to use for Y-axis values

    Returns:
        Dictionary with timestamps and values for line graph
    """
    timestamps = []
    values = []

    for task in tasks:
        start_str = task.get("start_date", "")
        if "start_time" in task and task.get("start_time"):
            start_str = f"{start_str} {task['start_time']}"

        start_dt = parse_timestamp(start_str) if start_str else None

        if start_dt:
            # Try to extract numeric value from the specified field
            value = task.get(value_field, "")

            # If it's a duration like "5d", extract the number
            if value and isinstance(value, str):
                numeric_value: Optional[float] = None
                if value.endswith("d"):
                    try:
                        numeric_value = float(value[:-1]) * 24
                    except ValueError:
                        pass
                elif value.endswith("h"):
                    try:
                        numeric_value = float(value[:-1])
                    except ValueError:
                        pass
                else:
                    try:
                        numeric_value = float(value)
                    except ValueError:
                        pass

                if numeric_value is not None:
                    timestamps.append(start_dt.isoformat())
                    values.append(numeric_value)

    return {"timestamps": timestamps, "values": values}


def generate_html_visualization(
    csv_files_data: List[Dict[str, Any]],
    title: str = "Time-Synced Visualizations",
    show_timeline: bool = True,
    show_histogram: bool = True,
    show_line_graph: bool = True,
) -> str:
    """Generate interactive HTML with time-synchronized visualizations.

    Args:
        csv_files_data: List of dictionaries containing CSV data and metadata
                       Each dict should have:
                       {"name": str, "tasks": List[Dict[str, str]]}
        title: Title for the HTML page
        show_timeline: Whether to include timeline chart
        show_histogram: Whether to include histogram
        show_line_graph: Whether to include line graph

    Returns:
        HTML string with embedded Plotly.js visualizations
    """
    # Prepare data for all visualizations
    all_timeline_data = []
    all_histogram_data = []
    all_line_graph_data = []

    for file_data in csv_files_data:
        file_name = file_data.get("name", "Unknown")
        tasks = file_data.get("tasks", [])

        if show_timeline:
            timeline = prepare_timeline_data(tasks)
            all_timeline_data.append({"name": file_name, "data": timeline})

        if show_histogram:
            histogram = prepare_histogram_data(tasks)
            all_histogram_data.append({"name": file_name, "data": histogram})

        if show_line_graph:
            line_graph = prepare_line_graph_data(tasks)
            all_line_graph_data.append({"name": file_name, "data": line_graph})

    # Build file options for the filter dropdown
    file_options = []
    for i, file_data in enumerate(csv_files_data):
        name = file_data.get("name", f"File {i+1}")
        file_options.append(f'                <option value="{i}">{name}</option>')
    file_options_html = chr(10).join(file_options)

    # Build chart containers
    chart_containers = []
    if show_timeline:
        chart_containers.append(
            '<div class="chart-container">'
            '<div class="chart-title">Timeline Chart (Gantt View)</div>'
            '<div id="timeline-chart"></div></div>'
        )
    if show_histogram:
        chart_containers.append(
            '<div class="chart-container">'
            '<div class="chart-title">Event Histogram</div>'
            '<div id="histogram-chart"></div></div>'
        )
    if show_line_graph:
        chart_containers.append(
            '<div class="chart-container">'
            '<div class="chart-title">Line Graph</div>'
            '<div id="line-graph-chart"></div></div>'
        )
    charts_html = chr(10).join(chart_containers)

    # Generate HTML with embedded Plotly.js
    html_template = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>{title}</title>
    <script src="https://cdn.plot.ly/plotly-2.27.0.min.js"></script>
    <style>
        body {{
            font-family: Arial, sans-serif;
            margin: 20px;
            background-color: #f5f5f5;
        }}
        h1 {{
            text-align: center;
            color: #333;
        }}
        .chart-container {{
            background-color: white;
            border-radius: 8px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            margin: 20px 0;
            padding: 20px;
        }}
        .chart-title {{
            font-size: 18px;
            font-weight: bold;
            margin-bottom: 10px;
            color: #555;
        }}
        .controls {{
            margin: 20px 0;
            padding: 15px;
            background-color: white;
            border-radius: 8px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }}
        .filter-section {{
            margin: 10px 0;
        }}
        label {{
            margin-right: 10px;
            font-weight: bold;
        }}
        select, input {{
            padding: 5px;
            margin-right: 15px;
            border: 1px solid #ddd;
            border-radius: 4px;
        }}
        button {{
            padding: 8px 16px;
            background-color: #4CAF50;
            color: white;
            border: none;
            border-radius: 4px;
            cursor: pointer;
        }}
        button:hover {{
            background-color: #45a049;
        }}
    </style>
</head>
<body>
    <h1>{title}</h1>

    <div class="controls">
        <div class="filter-section">
            <label>Filter by CSV File:</label>
            <select id="fileFilter" onchange="updateFilters()">
                <option value="all">All Files</option>
{file_options_html}
            </select>

            <label>Filter by Task Name:</label>
            <input type="text" id="taskFilter" \
placeholder="Enter task name..." oninput="updateFilters()">

            <button onclick="resetFilters()">Reset Filters</button>
        </div>
    </div>

{charts_html}

    <script>
        // Data for visualizations
        const timelineData = {json.dumps(all_timeline_data)};
        const histogramData = {json.dumps(all_histogram_data)};
        const lineGraphData = {json.dumps(all_line_graph_data)};

        let currentFileFilter = 'all';
        let currentTaskFilter = '';

        // Create timeline chart (Gantt-like)
        function createTimelineChart(filteredData) {{
            if (!{str(show_timeline).lower()}) return;

            const traces = [];
            filteredData.forEach((fileData, idx) => {{
                fileData.data.forEach(item => {{
                    traces.push({{
                        x: [item.start, item.end],
                        y: [item.task, item.task],
                        mode: 'lines',
                        line: {{
                            width: 20,
                            color: `hsl(${{idx * 60}}, 70%, 60%)`
                        }},
                        name: fileData.name,
                        legendgroup: fileData.name,
                        showlegend: traces.length === 0,
                        hovertemplate: `<b>${{item.task}}</b><br>` +
                                     `Start: ${{item.start}}<br>` +
                                     `End: ${{item.end}}<br>` +
                                     `<extra>${{fileData.name}}</extra>`
                    }});
                }});
            }});

            const layout = {{
                xaxis: {{
                    title: 'Time',
                    type: 'date',
                    rangeslider: {{}},
                }},
                yaxis: {{
                    title: 'Tasks',
                    autorange: 'reversed'
                }},
                hovermode: 'closest',
                height: 400,
                margin: {{ l: 150, r: 50, t: 30, b: 50 }}
            }};

            Plotly.newPlot('timeline-chart', traces, layout, {{responsive: true}});

            // Store the chart element for sync
            document.getElementById('timeline-chart').on('plotly_relayout', syncZoom);
        }}

        // Create histogram chart
        function createHistogramChart(filteredData) {{
            if (!{str(show_histogram).lower()}) return;

            const traces = filteredData.map((fileData, idx) => ({{
                x: fileData.data.bins,
                y: fileData.data.counts,
                type: 'bar',
                name: fileData.name,
                marker: {{
                    color: `hsl(${{idx * 60}}, 70%, 60%)`
                }}
            }}));

            const layout = {{
                xaxis: {{
                    title: 'Time',
                    type: 'date'
                }},
                yaxis: {{
                    title: 'Event Count'
                }},
                barmode: 'stack',
                height: 300,
                margin: {{ l: 50, r: 50, t: 30, b: 50 }}
            }};

            Plotly.newPlot('histogram-chart', traces, layout, {{responsive: true}});

            document.getElementById('histogram-chart').on('plotly_relayout', syncZoom);
        }}

        // Create line graph chart
        function createLineGraphChart(filteredData) {{
            if (!{str(show_line_graph).lower()}) return;

            const traces = filteredData.map((fileData, idx) => ({{
                x: fileData.data.timestamps,
                y: fileData.data.values,
                type: 'scatter',
                mode: 'lines+markers',
                name: fileData.name,
                line: {{
                    color: `hsl(${{idx * 60}}, 70%, 60%)`
                }}
            }}));

            const layout = {{
                xaxis: {{
                    title: 'Time',
                    type: 'date'
                }},
                yaxis: {{
                    title: 'Value'
                }},
                height: 300,
                margin: {{ l: 50, r: 50, t: 30, b: 50 }}
            }};

            Plotly.newPlot('line-graph-chart', traces, layout, {{responsive: true}});

            document.getElementById('line-graph-chart').on('plotly_relayout', syncZoom);
        }}

        // Synchronize zoom across all charts
        let isSyncing = false;
        function syncZoom(eventData) {{
            if (isSyncing) return;
            if (!eventData['xaxis.range[0]'] && !eventData['xaxis.range']) return;

            isSyncing = true;

            const xRange = eventData['xaxis.range'] || [
                eventData['xaxis.range[0]'],
                eventData['xaxis.range[1]']
            ];

            const chartIds = ['timeline-chart', 'histogram-chart', 'line-graph-chart'];
            chartIds.forEach(id => {{
                const element = document.getElementById(id);
                if (element && element.data) {{
                    Plotly.relayout(id, {{'xaxis.range': xRange}});
                }}
            }});

            setTimeout(() => {{ isSyncing = false; }}, 100);
        }}

        // Filter data based on current filters
        function getFilteredData(data) {{
            return data.filter((fileData, idx) => {{
                if (currentFileFilter !== 'all' &&
                    idx !== parseInt(currentFileFilter)) {{
                    return false;
                }}

                if (currentTaskFilter) {{
                    const filterLower = currentTaskFilter.toLowerCase();
                    return fileData.data.some(item =>
                        (item.task && item.task.toLowerCase().includes(filterLower))
                    );
                }}

                return true;
            }}).map(fileData => {{
                if (!currentTaskFilter) return fileData;

                const filterLower = currentTaskFilter.toLowerCase();
                return {{
                    ...fileData,
                    data: fileData.data.filter(item =>
                        item.task && item.task.toLowerCase().includes(filterLower)
                    )
                }};
            }});
        }}

        // Update filters and redraw charts
        function updateFilters() {{
            currentFileFilter = document.getElementById('fileFilter').value;
            currentTaskFilter = document.getElementById('taskFilter').value;

            const filteredTimeline = getFilteredData(timelineData);
            const filteredHistogram = getFilteredData(histogramData);
            const filteredLineGraph = getFilteredData(lineGraphData);

            createTimelineChart(filteredTimeline);
            createHistogramChart(filteredHistogram);
            createLineGraphChart(filteredLineGraph);
        }}

        // Reset all filters
        function resetFilters() {{
            document.getElementById('fileFilter').value = 'all';
            document.getElementById('taskFilter').value = '';
            updateFilters();
        }}

        // Initial render
        updateFilters();
    </script>
</body>
</html>"""

    return html_template


def convert_csv_files_to_html(
    csv_files: List[Dict[str, str]],
    title: str = "Time-Synced Visualizations",
    show_timeline: bool = True,
    show_histogram: bool = True,
    show_line_graph: bool = True,
    verbose: bool = False,
    combine_threshold: Optional[int] = 60,
) -> str:
    """Convert multiple CSV files to HTML with time-synced visualizations.

    Args:
        csv_files: List of dictionaries with "name" and "content" keys
        title: Title for the HTML page
        show_timeline: Whether to include timeline chart
        show_histogram: Whether to include histogram
        show_line_graph: Whether to include line graph
        verbose: Whether to print verbose logging
        combine_threshold: Threshold for combining tasks
                          (passed to parse_csv)

    Returns:
        HTML string with time-synced visualizations
    """
    csv_files_data = []

    for csv_file in csv_files:
        file_name = csv_file.get("name", "Unknown")
        csv_content = csv_file.get("content", "")

        # Parse CSV and prepare tasks
        tasks = parse_csv(csv_content, verbose)

        # Combine tasks if threshold is set
        if combine_threshold is not None:
            from . import combine_tasks_by_name

            tasks = combine_tasks_by_name(tasks, combine_threshold, verbose)

        csv_files_data.append({"name": file_name, "tasks": tasks})

    return generate_html_visualization(
        csv_files_data,
        title=title,
        show_timeline=show_timeline,
        show_histogram=show_histogram,
        show_line_graph=show_line_graph,
    )
