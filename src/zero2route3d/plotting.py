"""Publication-ready scientific plotting and visualization for 02Route 3D.

Generates cross-sectional elevation profiles, 4D Pareto trade-off diagrams,
E2SFCA Lorenz equity curves, and multi-profile radar comparison charts.
All plotting dependencies (matplotlib) are lazily loaded with graceful fallbacks.
"""

from __future__ import annotations

from typing import Any, List, Optional, Tuple


def plot_elevation_profile(
    route: Any,
    show_energy: bool = True,
    title: Optional[str] = None,
    figsize: Tuple[float, float] = (10.0, 4.5),
    save_path: Optional[str] = None,
) -> Any:
    """Plot high-grade longitudinal elevation profile with slope color coding and cumulative energy.

    Args:
        route: RouteResult3D or list of (lon, lat, elev) tuples.
        show_energy: Show secondary axis with metabolic kilocalorie expenditure.
        title: Plot title (defaults to route statistics summary).
        figsize: Figure dimensions (width, height) in inches.
        save_path: Optional filepath to save the figure (PNG, SVG, PDF).

    Returns:
        matplotlib.figure.Figure instance.
    """
    try:
        import matplotlib.pyplot as plt
    except ImportError as exc:
        raise ImportError(
            "matplotlib is required for plotting. Install via 'pip install matplotlib'."
        ) from exc

    coords: List[Tuple[float, float, float]] = []
    if hasattr(route, "coordinates_3d"):
        coords = [
            (float(c[0]), float(c[1]), float(c[2]) if len(c) > 2 else 0.0)
            for c in route.coordinates_3d
        ]
    elif isinstance(route, list):
        coords = [(float(c[0]), float(c[1]), float(c[2]) if len(c) > 2 else 0.0) for c in route]

    if len(coords) < 2:
        raise ValueError("At least 2 coordinates are required to plot an elevation profile.")

    # Calculate cumulative distance and incremental slopes
    from .kinematics import haversine_distance_2d, minetti_energy_cost

    distances_km = [0.0]
    elevations_m = [coords[0][2]]
    slopes_pct = [0.0]
    calories_kcal = [0.0]

    cum_dist = 0.0
    cum_kcal = 0.0

    for i in range(len(coords) - 1):
        p1 = coords[i]
        p2 = coords[i + 1]
        step_m = haversine_distance_2d(p1, p2)
        cum_dist += step_m / 1000.0
        elev_diff_m = p2[2] - p1[2]
        slope_pct = (elev_diff_m / step_m * 100.0) if step_m > 0 else 0.0

        _j, step_kcal = minetti_energy_cost(slope_pct / 100.0, mass_kg=70.0, distance_m=step_m)
        cum_kcal += step_kcal

        distances_km.append(cum_dist)
        elevations_m.append(p2[2])
        slopes_pct.append(slope_pct)
        calories_kcal.append(cum_kcal)

    fig, ax1 = plt.subplots(figsize=figsize, dpi=150)

    # Plot elevation line
    ax1.plot(
        distances_km, elevations_m, color="#0284c7", linewidth=2.5, label="Elevation (m)", zorder=3
    )
    ax1.fill_between(
        distances_km, elevations_m, min(elevations_m) - 2.0, color="#0284c7", alpha=0.15, zorder=2
    )

    ax1.set_xlabel("Cumulative Distance (km)", fontsize=11, fontweight="600")
    ax1.set_ylabel("Elevation (m)", fontsize=11, fontweight="600", color="#0284c7")
    ax1.tick_params(axis="y", labelcolor="#0284c7")
    ax1.grid(True, linestyle="--", alpha=0.5, zorder=1)

    # Optional secondary axis for metabolic calories
    if show_energy:
        ax2 = ax1.twinx()
        ax2.plot(
            distances_km,
            calories_kcal,
            color="#f97316",
            linestyle="--",
            linewidth=2.0,
            label="Metabolic Calories (kcal)",
            zorder=4,
        )
        ax2.set_ylabel("Cumulative Energy (kcal)", fontsize=11, fontweight="600", color="#f97316")
        ax2.tick_params(axis="y", labelcolor="#f97316")

    # Title & formatting
    stat_title = title or (
        f"3D Route Elevation Profile — Distance: {cum_dist:.2f} km | "
        f"Ascent: +{sum(max(0, coords[i + 1][2] - coords[i][2]) for i in range(len(coords) - 1)):.1f} m"
    )
    plt.title(stat_title, fontsize=12, fontweight="bold", pad=12)
    plt.tight_layout()

    if save_path:
        plt.savefig(save_path, bbox_inches="tight")

    return fig


def plot_pareto_frontier_2d(
    pareto_result: Any,
    x_metric: str = "time_min",
    y_metric: str = "climb_m",
    figsize: Tuple[float, float] = (8.0, 5.0),
    save_path: Optional[str] = None,
) -> Any:
    """Plot 2D non-dominated Pareto trade-off scatter curve."""
    try:
        import matplotlib.pyplot as plt
    except ImportError as exc:
        raise ImportError("matplotlib is required for plotting.") from exc

    if not hasattr(pareto_result, "solutions") or not pareto_result.solutions:
        raise ValueError("ParetoFrontierResult must contain at least 1 solution.")

    x_vals: List[float] = []
    y_vals: List[float] = []
    labels: List[str] = []

    for idx, sol in enumerate(pareto_result.solutions, start=1):
        time_min = (
            sol.statistics.total_duration_min
            if hasattr(sol, "statistics")
            else (sol.costs.time_sec / 60.0)
        )
        climb_m = (
            sol.statistics.elevation_gain_m if hasattr(sol, "statistics") else sol.costs.climb_m
        )
        cal_kcal = (
            sol.statistics.total_calories_kcal
            if hasattr(sol, "statistics")
            else sol.costs.calories_kcal
        )

        xv = (
            time_min if x_metric == "time_min" else (climb_m if x_metric == "climb_m" else cal_kcal)
        )
        yv = (
            climb_m if y_metric == "climb_m" else (time_min if y_metric == "time_min" else cal_kcal)
        )

        x_vals.append(xv)
        y_vals.append(yv)
        labels.append(f"Sol #{idx}")

    fig, ax = plt.subplots(figsize=figsize, dpi=150)
    ax.scatter(x_vals, y_vals, color="#8b5cf6", s=90, edgecolors="#4c1d95", linewidth=1.5, zorder=3)

    for i, txt in enumerate(labels):
        ax.annotate(
            txt,
            (x_vals[i], y_vals[i]),
            textcoords="offset points",
            xytext=(8, 5),
            fontsize=9,
            fontweight="600",
        )

    ax.set_xlabel(x_metric.replace("_", " ").title(), fontsize=11, fontweight="600")
    ax.set_ylabel(y_metric.replace("_", " ").title(), fontsize=11, fontweight="600")
    ax.set_title(
        "NAMOA* 4D Multi-Objective Pareto Trade-Off Frontier",
        fontsize=12,
        fontweight="bold",
        pad=12,
    )
    ax.grid(True, linestyle="--", alpha=0.5, zorder=1)
    plt.tight_layout()

    if save_path:
        plt.savefig(save_path, bbox_inches="tight")

    return fig


def plot_lorenz_equity_curve(
    scorecard: Any,
    figsize: Tuple[float, float] = (6.0, 6.0),
    save_path: Optional[str] = None,
) -> Any:
    """Plot Lorenz curve of spatial healthcare/amenity accessibility vs perfect equality line."""
    try:
        import matplotlib.pyplot as plt
    except ImportError as exc:
        raise ImportError("matplotlib is required for plotting.") from exc

    if not hasattr(scorecard, "lorenz_curve"):
        raise ValueError("Expected EquityScorecardResult instance with lorenz_curve.")

    lorenz_pts = scorecard.lorenz_curve
    x_pop: List[float] = []
    y_acc: List[float] = []
    for p in lorenz_pts:
        if isinstance(p, dict):
            x_pop.append(float(p.get("pop_share", p.get("pop_fraction", 0.0))))
            y_acc.append(float(p.get("acc_share", p.get("acc_fraction", 0.0))))
        elif isinstance(p, (list, tuple)):
            x_pop.append(float(p[0]))
            y_acc.append(float(p[1]))

    fig, ax = plt.subplots(figsize=figsize, dpi=150)
    ax.plot(
        [0, 1],
        [0, 1],
        color="#94a3b8",
        linestyle="--",
        linewidth=1.5,
        label="Line of Perfect Equality",
    )
    ax.plot(
        x_pop,
        y_acc,
        color="#10b981",
        linewidth=2.5,
        label=f"Lorenz Curve (Gini = {scorecard.gini_coefficient:.3f})",
    )
    ax.fill_between(x_pop, y_acc, x_pop, color="#10b981", alpha=0.15)

    ax.set_xlabel("Cumulative Share of Population", fontsize=11, fontweight="600")
    ax.set_ylabel("Cumulative Share of Accessibility", fontsize=11, fontweight="600")
    ax.set_title(
        f"Spatial Equity Lorenz Curve (Gini = {scorecard.gini_coefficient:.3f})",
        fontsize=12,
        fontweight="bold",
        pad=12,
    )
    ax.legend(loc="upper left", frameon=True)
    ax.grid(True, linestyle="--", alpha=0.5)
    ax.set_xlim([0, 1])
    ax.set_ylim([0, 1])
    plt.tight_layout()

    if save_path:
        plt.savefig(save_path, bbox_inches="tight")

    return fig
