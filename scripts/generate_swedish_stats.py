#!/usr/bin/env python3
"""
Generate year-over-year statistics for Swedish MTBO events (2010-2025).
Outputs a summary table and generates charts for:
1. Annual Overview (Events & Participants)
2. Seasonality (Events per month)
3. Detailed Event Timeline (Stacked participant counts)
"""

import json
import sys
from collections import defaultdict
from datetime import date, datetime
from pathlib import Path
from typing import TypedDict, cast

# Add project root to path for imports
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import matplotlib.pyplot as plt
import numpy as np

from src.models import EventDict, RaceDict

# Configuration
DATA_DIR = Path("data/events")
OUTPUT_DIR = Path("artifacts/stats")
START_YEAR = 2010
END_YEAR = 2025

# Ensure output directory exists
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


class RaceData(TypedDict):
    year: int
    date: date
    name: str
    participants: int
    month: int


class AnnualStats(TypedDict):
    year: int
    event_count: int
    participant_count: int
    events: list[RaceData]


def load_events(year: int) -> list[EventDict]:
    filepath = DATA_DIR / str(year) / "events.json"
    if not filepath.exists():
        print(f"Warning: Data file not found for {year}: {filepath}")
        return []

    try:
        with open(filepath, encoding="utf-8") as f:
            data = json.load(f)
            return cast(list[EventDict], data.get("events", []))
    except json.JSONDecodeError:
        print(f"Error: Failed to parse JSON for {year}")
        return []


def is_swedish_event(event: EventDict) -> bool:
    for organiser in event.get("organisers", []):
        if organiser.get("country_code") == "SWE":
            return True
    return False


def should_skip_event(event: EventDict) -> bool:
    tags = event.get("tags", [])
    return "EVENT_SKIP" in tags


def get_race_participant_count(race: RaceDict) -> int:
    fingerprints = race.get("fingerprints", [])
    if fingerprints:
        return len(fingerprints)

    s_counts = race.get("start_counts")
    r_counts = race.get("result_counts")

    if s_counts:
        return sum(s_counts.values())
    elif r_counts:
        return sum(r_counts.values())

    return 0


def process_data() -> tuple[list[AnnualStats], list[RaceData]]:
    annual_stats: list[AnnualStats] = []
    all_races_flat: list[RaceData] = []

    print(f"Processing years {START_YEAR} to {END_YEAR}...")

    for year in range(START_YEAR, END_YEAR + 1):
        events = load_events(year)

        year_event_count = 0
        year_participant_count = 0
        year_races = []

        for event in events:
            if is_swedish_event(event) and not should_skip_event(event):
                year_event_count += 1

                # Check for races
                races = event.get("races", [])
                if not races:
                    # Fallback for old events without races?
                    # If strictly adhering to schema, races should exist.
                    # If not, we might miss data.
                    # Assuming races exist or we skip.
                    continue

                for race in races:
                    p_count = get_race_participant_count(race)
                    year_participant_count += p_count

                    # Get Race Date
                    # Try race['datetimez'] first
                    # Fallback to event['start_time']
                    date_val = None
                    dt_str = race.get("datetimez")
                    if dt_str:
                        try:
                            # Parse ISO format "2010-04-16T00:00:00+00:00"
                            # We only care about the date part
                            date_val = datetime.fromisoformat(dt_str).date()
                        except (ValueError, TypeError):
                            pass

                    if not date_val:
                        # Fallback to event date
                        start_date_str = event.get("start_time")
                        if not start_date_str:
                            continue

                        try:
                            date_val = datetime.strptime(
                                start_date_str, "%Y-%m-%d"
                            ).date()
                        except (ValueError, TypeError):
                            continue

                    # Race Name
                    # Often "Race 1", "Stage 1", or full name.
                    # If race name is generic (e.g. "1"), prepend event name?
                    r_name = race.get("name", "")
                    e_name = event.get("name", "")

                    # Heuristic: simple check (like if race name is in event name)
                    # Many races have full names.
                    # Let's use: Event Name - Race Name
                    if e_name in r_name:
                        display_name = r_name
                    else:
                        display_name = f"{e_name} - {r_name}"

                    race_data: RaceData = {
                        "year": year,
                        "date": date_val,
                        "name": display_name,
                        "participants": p_count,
                        "month": date_val.month,
                    }

                    year_races.append(race_data)
                    all_races_flat.append(race_data)

        annual_stats.append(
            {
                "year": year,
                "event_count": year_event_count,
                "participant_count": year_participant_count,
                "events": year_races,
            }
        )

    return annual_stats, all_races_flat


def print_summary_table(annual_stats: list[AnnualStats]) -> None:
    print("\n### Annual Summary Table\n")
    print("| Year | Events | Participants (Starts) |")
    print("|------|--------|-----------------------|")
    for stat in annual_stats:
        print(
            f"| {stat['year']} | {stat['event_count']} | {stat['participant_count']} |"
        )


def plot_annual_overview(annual_stats: list[AnnualStats]) -> None:
    years = [s["year"] for s in annual_stats]
    events = [s["event_count"] for s in annual_stats]
    participants = [s["participant_count"] for s in annual_stats]

    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(10, 10), sharex=True)

    # Events
    bars1 = ax1.bar(years, events, color="skyblue", label="Events")
    ax1.set_ylabel("Number of Events")
    ax1.set_title("Total Swedish MTBO Events per Year")
    ax1.bar_label(bars1)
    ax1.grid(axis="y", linestyle="--", alpha=0.7)

    # Participants
    bars2 = ax2.bar(years, participants, color="salmon", label="Participants")
    ax2.set_ylabel("Total Starts")
    ax2.set_title("Total Participants (Starts) per Year")
    ax2.set_xlabel("Year")
    ax2.bar_label(bars2)
    ax2.grid(axis="y", linestyle="--", alpha=0.7)

    plt.xticks(years, rotation=45)
    plt.tight_layout()
    plt.savefig(OUTPUT_DIR / "stats_annual_summary.png")
    print(f"Saved annual overview to {OUTPUT_DIR / 'stats_annual_summary.png'}")
    plt.close()


def plot_seasonality(annual_stats: list[AnnualStats]) -> None:
    # Prepare data: years as columns, months as rows
    months = np.arange(1, 13)
    years = [s["year"] for s in annual_stats]

    # Organize count of PARTICIPANTS per month per year
    monthly_counts = {year: [0] * 12 for year in years}

    for stat in annual_stats:
        year = stat["year"]
        for event in stat["events"]:
            m = event["month"]
            p = event.get("participants", 0)
            if 1 <= m <= 12:
                monthly_counts[year][m - 1] += p

    fig, ax = plt.subplots(figsize=(14, 8))

    width = 0.8 / len(years)
    # Using a colormap
    colors = plt.cm.tab20(np.linspace(0, 1, len(years)))

    for i, year in enumerate(years):
        counts = monthly_counts[year]
        # Offset bars
        offset = (i - len(years) / 2) * width + width / 2
        ax.bar(months + offset, counts, width=width, label=str(year), color=colors[i])

    ax.set_xlabel("Month")
    ax.set_ylabel("Number of Participants (Starts)")
    ax.set_title("Seasonality: Participants per Month (Yearly Comparison)")
    ax.set_xticks(months)
    ax.set_xticklabels(
        [
            "Jan",
            "Feb",
            "Mar",
            "Apr",
            "May",
            "Jun",
            "Jul",
            "Aug",
            "Sep",
            "Oct",
            "Nov",
            "Dec",
        ]
    )
    ax.legend(title="Year", bbox_to_anchor=(1.05, 1), loc="upper left")
    ax.grid(axis="y", linestyle="--", alpha=0.5)

    plt.tight_layout()
    plt.savefig(OUTPUT_DIR / "stats_seasonality.png")
    print(f"Saved seasonality chart to {OUTPUT_DIR / 'stats_seasonality.png'}")
    plt.close()


def plot_detailed_timeline(all_events: list[RaceData]) -> None:
    # Filter out events with 0 participants for the timeline visualization
    valid_events = [e for e in all_events if e["participants"] > 0]

    # Group by date
    events_by_date = defaultdict(list)
    for e in valid_events:
        events_by_date[e["date"]].append(e)

    sorted_dates = sorted(events_by_date.keys())

    # Generate one chart PER YEAR
    # Use original all_events to determine year range? No, just valid ones.
    if not sorted_dates:
        return

    years = sorted({d.year for d in sorted_dates})

    for year in years:
        # Filter dates for this specific year
        year_dates = [d for d in sorted_dates if d.year == year]

        if not year_dates:
            continue

        # Calculate total for THIS year's valid events
        year_total = sum(e["participants"] for e in valid_events if e["year"] == year)

        # Dynamic width based on number of dates
        n_dates = len(year_dates)
        width_in = max(15, n_dates * 0.25)

        fig, ax = plt.subplots(figsize=(width_in, 10))
        plt.subplots_adjust(bottom=0.5, top=0.9)

        # Categorical X-axis
        x_positions = np.arange(n_dates)

        # Plot stacked bars
        x_labels = []

        for i, event_date in enumerate(year_dates):
            day_events = events_by_date[event_date]
            # Sort alphabetical
            day_events.sort(key=lambda x: x["name"])

            bottom = 0
            names_list = []
            for event in day_events:
                p_count = event["participants"]
                # p_count > 0 is guaranteed by valid_events filter

                # Plot bar at integer position i
                ax.bar(
                    i,
                    p_count,
                    bottom=bottom,
                    width=0.8,
                    color="skyblue",
                    edgecolor="black",
                    alpha=0.8,
                )
                bottom += p_count

                names_list.append(f"{event['name']} ({p_count})")

            # Create label string: Date + Names
            date_str = event_date.strftime("%m-%d")
            label_text = f"{date_str} " + " / ".join(names_list)
            x_labels.append(label_text)

        # Add Year Text at top
        ax.text(
            0.5,
            0.95,
            str(year),
            transform=ax.transAxes,
            fontsize=20,
            fontweight="bold",
            ha="center",
            va="top",
            color="dimgrey",
        )

        ax.set_ylabel("Participants (Starts)")
        # Add Total to Title
        ax.set_title(
            f"Event Participation Timeline - {year} (Total Starts: {year_total})"
        )

        # Set X-Axis Ticks and Labels
        ax.set_xticks(x_positions)
        ax.set_xticklabels(x_labels, rotation=45, ha="right", fontsize=9)

        # Limit x-axis to tight range
        ax.set_xlim(-0.6, n_dates - 0.4)

        ax.grid(axis="y", linestyle="--", alpha=0.5)

        filename = f"stats_events_detail_{year}.png"
        plt.savefig(OUTPUT_DIR / filename)
        print(f"Saved detailed timeline to {OUTPUT_DIR / filename}")
        plt.close()


def main() -> None:
    if not hasattr(plt, "subplots"):
        print("Error: Matplotlib not properly installed or headless mode issue.")
        return

    annual_stats, all_events = process_data()

    if not annual_stats:
        print("No data found.")
        return

    print_summary_table(annual_stats)

    print("\nGenerating charts...")
    plot_annual_overview(annual_stats)
    plot_seasonality(annual_stats)
    plot_detailed_timeline(all_events)
    print("\nDone. Check artifacts/stats/ for images.")


if __name__ == "__main__":
    main()
