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
    unique_participant_count: int
    unique_swe_count: int
    unique_iof_additional_count: int
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
        swe_fps = set()
        iof_fps = set()
        year_races = []

        for event in events:
            if is_swedish_event(event) and not should_skip_event(event):
                year_event_count += 1

                # Check for races
                races = event.get("races", [])
                if not races:
                    continue

                for race in races:
                    p_count = get_race_participant_count(race)
                    year_participant_count += p_count

                    # Track unique participants by source
                    fps = race.get("fingerprints", [])
                    if event["id"].startswith("SWE_"):
                        swe_fps.update(fps)
                    elif event["id"].startswith("IOF_"):
                        iof_fps.update(fps)

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

        combined = swe_fps | iof_fps
        annual_stats.append(
            {
                "year": year,
                "event_count": year_event_count,
                "participant_count": year_participant_count,
                "unique_participant_count": len(combined),
                "unique_swe_count": len(swe_fps),
                "unique_iof_additional_count": len(iof_fps - swe_fps),
                "events": year_races,
            }
        )

    return annual_stats, all_races_flat


def print_summary_table(annual_stats: list[AnnualStats]) -> None:
    print("\n### Annual Summary Table\n")
    print(
        "| Year | Events | Starts | Unique (Total) | Unique (SWE) | Unique (IOF-only) |"
    )
    print(
        "|------|--------|--------|----------------|--------------|-------------------|"
    )
    for stat in annual_stats:
        print(
            f"| {stat['year']} | {stat['event_count']} | "
            f"{stat['participant_count']:>6} | "
            f"{stat['unique_participant_count']:>14} | "
            f"{stat['unique_swe_count']:>12} | "
            f"{stat['unique_iof_additional_count']:>17} |"
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


def plot_unique_participants(annual_stats: list[AnnualStats]) -> None:
    years = [s["year"] for s in annual_stats]
    swe_counts = [s["unique_swe_count"] for s in annual_stats]
    iof_additional = [s["unique_iof_additional_count"] for s in annual_stats]

    # Professional color palette
    swe_color = "#4A90D9"  # Harmonious blue
    iof_color = "#FFB347"  # Soft orange for highlights

    fig, ax = plt.subplots(figsize=(12, 7))
    plt.subplots_adjust(bottom=0.12, top=0.90, left=0.08, right=0.95)

    # Vertical stacked bars
    ax.bar(
        years,
        swe_counts,
        color=swe_color,
        label="Swedish events",
        edgecolor="white",
        linewidth=0.5,
    )
    ax.bar(
        years,
        iof_additional,
        bottom=swe_counts,
        color=iof_color,
        label="IOF events",
        edgecolor="white",
        linewidth=0.5,
    )

    ax.set_ylabel("Number of participants", fontsize=11, labelpad=10)
    ax.set_xlabel("Year", fontsize=11, labelpad=10)
    ax.set_title(
        "Unique Swedish MTBO Participants (2010–2025)",
        fontsize=14,
        fontweight="bold",
        pad=20,
    )

    # Add labels for total on top of bars
    totals = []
    for i, year in enumerate(years):
        total = swe_counts[i] + iof_additional[i]
        totals.append(total)
        if total > 0:
            ax.text(
                year,
                total + 15,
                f"{total:,}",
                ha="center",
                va="bottom",
                fontsize=9,
                fontweight="bold",
                color="#444444",
            )

    # Legend at top left
    ax.legend(frameon=False, loc="upper left", fontsize=10)

    # Gridlines — visible horizontal bars every 1000
    ax.grid(
        axis="y",
        which="major",
        linestyle="-",
        linewidth=0.5,
        alpha=0.4,
        color="#888888",
    )
    ax.set_axisbelow(True)

    # Remove top and right spines
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.spines["left"].set_color("#cccccc")
    ax.spines["bottom"].set_color("#cccccc")

    # Remove tick notches but keep labels
    ax.tick_params(axis="y", which="both", length=0)

    # Y-axis limit and ticks (every 1000)
    if totals:
        max_total = max(totals)
        ax.set_ylim(0, max_total * 1.15)
        yticks = np.arange(0, max_total * 1.2, 1000)
        ax.set_yticks(yticks)

    plt.xticks(years, rotation=45, fontsize=10)
    plt.yticks(fontsize=10)

    filename = "stats_unique_participants.png"
    plt.savefig(OUTPUT_DIR / filename, dpi=120)
    print(f"Saved unique participants chart to {OUTPUT_DIR / filename}")
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


def _shorten_event_name(name: str) -> str:
    """Shorten event names for readable axis labels.

    Strips 'MTBO' prefix/suffix, common noise, and truncates long names.
    """
    import re

    # Remove common prefixes: "MTBO, ", "MTBO - ", "MTBO " at start
    name = re.sub(r"^MTBO[\s,\-]+", "", name, flags=re.IGNORECASE)
    # Remove " - MTBO" suffix or ", MTBO" etc.
    name = re.sub(r"[\s,\-]+MTBO$", "", name, flags=re.IGNORECASE)
    # Remove standalone "MTBO" if it's the only remaining word
    name = re.sub(r"^MTBO$", "MTBO", name, flags=re.IGNORECASE)
    # Strip leading/trailing separators
    name = name.strip(" ,-/")
    # Truncate at 35 chars
    if len(name) > 35:
        name = name[:32] + "…"
    return name


def plot_detailed_timeline(all_events: list[RaceData]) -> None:
    # Include ALL events (including 0 participants)
    events_by_date: dict[date, list[RaceData]] = defaultdict(list)
    for e in all_events:
        events_by_date[e["date"]].append(e)

    sorted_dates = sorted(events_by_date.keys())

    if not sorted_dates:
        return

    years = sorted({d.year for d in sorted_dates})

    # Color palette for stacked segments
    bar_colors = ["#4A90D9", "#6BAED6", "#9ECAE1", "#C6DBEF", "#DEEBF7"]

    for year in years:
        year_dates = [d for d in sorted_dates if d.year == year]

        if not year_dates:
            continue

        year_total = sum(e["participants"] for e in all_events if e["year"] == year)
        year_event_count = sum(len(events_by_date[d]) for d in year_dates)

        n_dates = len(year_dates)
        width_in = max(16, n_dates * 0.3)

        fig, ax = plt.subplots(figsize=(width_in, 7))
        plt.subplots_adjust(bottom=0.08, top=0.90, left=0.05, right=0.97)

        max_height = 0

        for i, event_date in enumerate(year_dates):
            day_events = events_by_date[event_date]
            day_events.sort(key=lambda x: x["name"])

            bottom = 0
            for j, event in enumerate(day_events):
                p_count = event["participants"]
                bar_h = max(p_count, 2)  # Minimum bar height for visibility

                color = bar_colors[j % len(bar_colors)]
                ax.bar(
                    i,
                    bar_h,
                    bottom=bottom,
                    width=0.75,
                    color=color,
                    edgecolor="white",
                    linewidth=0.5,
                )
                bottom += bar_h

            max_height = max(max_height, bottom)

        # Gridlines at every 100
        grid_max = int(max_height / 100 + 1) * 100
        ax.set_yticks(range(0, grid_max + 1, 100))
        ax.yaxis.set_minor_locator(plt.MultipleLocator(50))
        ax.grid(
            axis="y",
            which="major",
            linestyle="-",
            linewidth=0.5,
            alpha=0.4,
            color="#888888",
        )
        ax.grid(
            axis="y",
            which="minor",
            linestyle=":",
            linewidth=0.3,
            alpha=0.3,
            color="#aaaaaa",
        )

        # Year watermark
        ax.text(
            0.5,
            0.5,
            str(year),
            transform=ax.transAxes,
            fontsize=80,
            fontweight="bold",
            ha="center",
            va="center",
            color="#e0e0e0",
            zorder=0,
        )

        ax.set_ylabel("Participants (Starts)", fontsize=11)
        ax.set_title(
            f"MTBO Event Timeline — {year}  "
            f"({year_event_count} races, {year_total} total starts)",
            fontsize=13,
            fontweight="bold",
            pad=12,
        )

        # X-axis — date labels
        x_positions = np.arange(n_dates)
        date_labels = [d.strftime("%m-%d") for d in year_dates]
        ax.set_xticks(x_positions)
        ax.set_xticklabels(date_labels, rotation=90, ha="center", fontsize=7)
        ax.set_xlim(-0.6, n_dates - 0.4)
        ax.set_ylim(bottom=0)

        # Remove top and right spines
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)

        filename = f"stats_events_detail_{year}.png"
        plt.savefig(OUTPUT_DIR / filename, dpi=100)
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
    plot_unique_participants(annual_stats)
    plot_seasonality(annual_stats)
    plot_detailed_timeline(all_events)
    print("\nDone. Check artifacts/stats/ for images.")


if __name__ == "__main__":
    main()
