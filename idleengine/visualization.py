from __future__ import annotations

from idleengine.report import SimulationReport


def plot_simulation(
    report: SimulationReport,
    output_path: str | None = None,
) -> None:
    """Generate a 4-panel matplotlib visualization of simulation results.

    Requires matplotlib (optional dependency).
    """
    try:
        import matplotlib.pyplot as plt
    except ImportError:
        raise ImportError(
            "matplotlib is required for visualization. "
            "Install with: pip install idleengine[viz]"
        )

    fig, axes = plt.subplots(2, 2, figsize=(14, 10))
    fig.suptitle(
        f"IdleEngine Simulation — {report.strategy_description}",
        fontsize=14,
    )

    # 1. Currency values over time (log scale)
    ax1 = axes[0][0]
    currency_ids = sorted(
        {s.currency_id for s in report.currency_snapshots}
    )
    for cid in currency_ids:
        series = report.currency_series(cid)
        if series:
            times, values = zip(*series)
            positive_values = [max(v, 1e-10) for v in values]
            ax1.plot(times, positive_values, label=cid)
    ax1.set_yscale("log")
    ax1.set_xlabel("Time (s)")
    ax1.set_ylabel("Value")
    ax1.set_title("Currency Values")
    ax1.legend(fontsize=8)
    ax1.grid(True, alpha=0.3)

    # 2. Production rates over time
    ax2 = axes[0][1]
    for cid in currency_ids:
        series = report.rate_series(cid)
        if series:
            times, rates = zip(*series)
            if any(r > 0 for r in rates):
                ax2.plot(times, rates, label=cid)
    ax2.set_xlabel("Time (s)")
    ax2.set_ylabel("Rate (/s)")
    ax2.set_title("Production Rates")
    ax2.legend(fontsize=8)
    ax2.grid(True, alpha=0.3)

    # 3. Purchase timeline
    ax3 = axes[1][0]
    if report.purchases:
        times = [p.time for p in report.purchases]
        elements = [p.element_id for p in report.purchases]
        element_types = sorted(set(elements))
        y_map = {e: i for i, e in enumerate(element_types)}
        ys = [y_map[e] for e in elements]
        ax3.scatter(times, ys, s=10, alpha=0.6)
        ax3.set_yticks(range(len(element_types)))
        ax3.set_yticklabels(element_types, fontsize=7)
        ax3.set_xlabel("Time (s)")
        ax3.set_title("Purchase Timeline")
        ax3.grid(True, alpha=0.3)

    # 4. Purchase gap histogram
    ax4 = axes[1][1]
    if report.purchase_gaps:
        ax4.hist(report.purchase_gaps, bins=min(30, len(report.purchase_gaps)), alpha=0.7)
        ax4.axvline(
            report.mean_purchase_gap,
            color="red",
            linestyle="--",
            label=f"Mean: {report.mean_purchase_gap:.1f}s",
        )
        ax4.set_xlabel("Gap (s)")
        ax4.set_ylabel("Count")
        ax4.set_title("Purchase Gap Distribution")
        ax4.legend()
        ax4.grid(True, alpha=0.3)

    plt.tight_layout()

    if output_path:
        plt.savefig(output_path, dpi=150)
    else:
        plt.show()
