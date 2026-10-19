#!/usr/bin/env python3
"""Create light/dark animated contribution grids for every GitHub activity year.

Uses GitHub's GraphQL contribution calendar (not raw commit history).
All calendar squares remain visible while a snake moves over each year.
"""

from __future__ import annotations

import json
import os
from datetime import date, datetime, timedelta, timezone
from html import escape
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


API_URL = "https://api.github.com/graphql"
COLORS = {
    "light": ("#e8edf2", "#a5e8f3", "#65d5e8", "#22b8d3", "#097c97"),
    "dark": ("#1f2a3d", "#17475d", "#126b88", "#0ea5c5", "#67e8f9"),
}
LEVELS = {
    "NONE": 0,
    "FIRST_QUARTILE": 1,
    "SECOND_QUARTILE": 2,
    "THIRD_QUARTILE": 3,
    "FOURTH_QUARTILE": 4,
}
GRID_X = 122
PITCH = 13
DOT_SIZE = 10
ROW_HEIGHT = 143
HEADER_HEIGHT = 55


def graphql(token: str, query: str, variables: dict) -> dict:
    payload = json.dumps({"query": query, "variables": variables}).encode("utf-8")
    request = Request(
        API_URL,
        data=payload,
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "Content-Type": "application/json",
            "User-Agent": "github-profile-all-time-snake",
        },
        method="POST",
    )
    try:
        with urlopen(request, timeout=35) as response:
            result = json.load(response)
    except (HTTPError, URLError, TimeoutError) as exc:
        raise RuntimeError(f"GitHub GraphQL request failed: {exc}") from exc
    if result.get("errors"):
        raise RuntimeError(f"GitHub GraphQL returned errors: {result['errors']}")
    if not result.get("data", {}).get("user"):
        raise RuntimeError("GitHub user not found or contributions unavailable")
    return result["data"]["user"]


def contribution_years(token: str, username: str, current_year: int) -> list[int]:
    query = """
    query($login: String!) {
      user(login: $login) {
        contributionsCollection { contributionYears }
      }
    }
    """
    user = graphql(token, query, {"login": username})
    years = user["contributionsCollection"]["contributionYears"]
    start = min(years) if years else current_year
    # Cover even intervening years without contributions.
    return list(range(start, current_year + 1))


def get_year(token: str, username: str, year: int) -> dict[date, tuple[int, int]]:
    query = """
    query($login: String!, $from: DateTime!, $to: DateTime!) {
      user(login: $login) {
        contributionsCollection(from: $from, to: $to) {
          contributionCalendar {
            weeks {
              contributionDays { date contributionCount contributionLevel }
            }
          }
        }
      }
    }
    """
    user = graphql(
        token,
        query,
        {
            "login": username,
            "from": f"{year}-01-01T00:00:00Z",
            "to": f"{year}-12-31T23:59:59Z",
        },
    )
    days = user["contributionsCollection"]["contributionCalendar"]["weeks"]
    result = {}
    for week in days:
        for entry in week["contributionDays"]:
            day = date.fromisoformat(entry["date"])
            if day.year == year:
                result[day] = (
                    LEVELS[entry["contributionLevel"]],
                    entry["contributionCount"],
                )
    return result


def year_grid(year: int, today: date, days: dict[date, tuple[int, int]], palette: str):
    start = date(year, 1, 1)
    first_sunday = start - timedelta(days=(start.weekday() + 1) % 7)
    last_day = min(date(year, 12, 31), today)
    last_saturday = last_day + timedelta(days=(5 - last_day.weekday()) % 7)
    columns = (last_saturday - first_sunday).days // 7 + 1
    points = []
    squares = []
    row_y = HEADER_HEIGHT + (year_grid.year_index * ROW_HEIGHT)
    grid_y = row_y + 19

    for week in range(columns):
        weekday_indices = range(7) if week % 2 == 0 else range(6, -1, -1)
        for weekday in weekday_indices:
            day = first_sunday + timedelta(days=week * 7 + weekday)
            if day.year != year or day > today:
                continue
            x = GRID_X + week * PITCH
            y = grid_y + weekday * PITCH
            level, count = days.get(day, (0, 0))
            squares.append(
                f'<rect x="{x}" y="{y}" width="{DOT_SIZE}" height="{DOT_SIZE}" '
                f'rx="2" fill="{COLORS[palette][level]}">'
                f'<title>{day.isoformat()}: {count} contribuições</title></rect>'
            )
            points.append((x + DOT_SIZE / 2, y + DOT_SIZE / 2))

    total = sum(count for day, (_, count) in days.items() if day <= today)
    labels = [
        f'<text x="26" y="{row_y + 38}" class="year">{year}</text>',
        f'<text x="26" y="{row_y + 56}" class="year-count">{total} contrib.</text>',
    ]
    return "\n".join(labels + squares), points, columns


def animation(year: int, points: list[tuple[float, float]]) -> tuple[str, str]:
    if not points:
        return "", ""
    duration = max(20, min(42, len(points) * 0.065))
    frames = []
    length = len(points) - 1
    for i, (x, y) in enumerate(points):
        percent = (i / length * 100) if length else 0
        frames.append(f'{percent:.4f}%{{transform:translate({x:g}px,{y:g}px)}}')
    if length == 0:
        frames.append(f'100%{{transform:translate({points[0][0]:g}px,{points[0][1]:g}px)}}')
    name = f"travel-{year}"
    css = (
        f'@keyframes {name}{{{"".join(frames)}}}'
        f'.head-{year},.tail1-{year},.tail2-{year}{{'
        f'animation:{name} {duration:g}s steps(1,end) infinite;'
        f'animation-fill-mode:backwards;}}'
        f'.tail1-{year}{{animation-delay:.08s;}}'
        f'.tail2-{year}{{animation-delay:.16s;}}'
    )
    shapes = (
        f'<circle class="tail2-{year}" cx="0" cy="0" r="3" fill="#0e7490"/>'
        f'<circle class="tail1-{year}" cx="0" cy="0" r="4" fill="#0891b2"/>'
        f'<circle class="head-{year}" cx="0" cy="0" r="5.5" '
        f'fill="#22d3ee" stroke="#083344" stroke-width="1.5"/>'
    )
    return css, shapes


def render(username: str, year_data: dict[int, dict], today: date, palette: str) -> str:
    years = sorted(year_data)
    if not years:
        raise ValueError("No years to render")
    width = 845
    height = HEADER_HEIGHT + ROW_HEIGHT * len(years) + 20
    background = "#0b1423" if palette == "dark" else "#ffffff"
    text_color = "#e2e8f0" if palette == "dark" else "#172b4d"
    secondary = "#94a3b8" if palette == "dark" else "#607085"
    line = "#2c3c53" if palette == "dark" else "#d9e2ec"
    grid = []
    css_rules = []
    snakes = []
    for index, year in enumerate(years):
        year_grid.year_index = index
        squares, points, _ = year_grid(year, today, year_data[year], palette)
        grid.append(squares)
        css, circles = animation(year, points)
        css_rules.append(css)
        snakes.append(circles)

    period = str(years[0]) if len(years) == 1 else f"{years[0]}–{years[-1]}"
    heading = f"Contribuições no GitHub · {period}"
    svg = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}" role="img" aria-label="{escape(heading)}">',
        f'<title>{escape(heading)}</title>',
        '<style>',
        f'.heading{{font:600 17px system-ui,sans-serif;fill:{text_color}}}',
        f'.year{{font:700 17px system-ui,sans-serif;fill:{text_color}}}',
        f'.year-count{{font:12px system-ui,sans-serif;fill:{secondary}}}',
        f'{ "".join(css_rules) }',
        '@media (prefers-reduced-motion:reduce){'
        + ",".join(f'.head-{y},.tail1-{y},.tail2-{y}' for y in years)
        + '{animation:none!important;opacity:0}}',
        '</style>',
        f'<rect width="{width}" height="{height}" fill="{background}" rx="12"/>',
        f'<text x="26" y="32" class="heading">{escape(heading)}</text>',
        f'<line x1="26" y1="44" x2="{width - 26}" y2="44" stroke="{line}"/>',
        *grid,
        *snakes,
        '</svg>',
    ]
    return "\n".join(svg) + "\n"


def main():
    token = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")
    username = os.environ.get("GH_USERNAME", "LuizHvD")
    if not token:
        raise SystemExit("Missing GH_TOKEN / GITHUB_TOKEN")
    today = datetime.now(timezone.utc).date()
    years = contribution_years(token, username, today.year)
    annual_data = {year: get_year(token, username, year) for year in years}
    out = Path("dist")
    out.mkdir(parents=True, exist_ok=True)
    for mode, filename in (
        ("light", "github-contribution-grid-snake.svg"),
        ("dark", "github-contribution-grid-snake-dark.svg"),
    ):
        (out / filename).write_text(
            render(username, annual_data, today, mode), encoding="utf-8"
        )
    print(
        f"Generated {years[0]}–{years[-1]} ("
        f"{sum(sum(c for _, c in v.values()) for v in annual_data.values())} "
        "visible GitHub contributions)"
    )


if __name__ == "__main__":
    main()
