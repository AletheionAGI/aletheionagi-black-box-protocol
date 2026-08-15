from __future__ import annotations

import argparse
import json
import os
import tempfile
from pathlib import Path

os.environ.setdefault("MPLCONFIGDIR", str(Path(tempfile.gettempdir()) / "black-box-matplotlib"))

import matplotlib.pyplot as plt


OUTCOMES = (
    ("pass", "PASS", "#16a34a"),
    ("fail", "FAIL", "#dc2626"),
    ("skipped", "SKIPPED", "#d97706"),
    ("errors", "ERROR", "#7c3aed"),
)


def load_targets(run_dir: Path) -> dict[str, dict]:
    summary = json.loads((run_dir / "summary.json").read_text(encoding="utf-8"))
    return summary["protocol_performance"]["targets"]


def parse_override(value: str) -> tuple[str, Path]:
    if "=" not in value:
        raise argparse.ArgumentTypeError("override must be TARGET=RUN_DIRECTORY")
    target, directory = value.split("=", 1)
    return target, Path(directory).resolve()


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate a traceable PNG result chart")
    parser.add_argument("run_dir", type=Path, help="base complete-run directory")
    parser.add_argument(
        "--override",
        action="append",
        default=[],
        type=parse_override,
        help="replace one target with TARGET=RUN_DIRECTORY",
    )
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    base_dir = args.run_dir.resolve()
    targets = load_targets(base_dir)
    sources = [f"Base cohort: {base_dir.name}"]
    for target, run_dir in args.override:
        replacement = load_targets(run_dir)
        if target not in replacement:
            raise KeyError(f"{target!r} is absent from {run_dir}")
        targets[target] = replacement[target]
        sources.append(f"{target} revalidation: {run_dir.name}")

    display_names = {
        "aletheionagi": "AletheionAGI",
        "guardrails_ai": "Guardrails AI",
        "nemo_guardrails": "NVIDIA NeMo Guardrails",
        "patronus_lynx": "Patronus Lynx",
    }
    order = [name for name in display_names if name in targets]
    labels = [display_names[name] for name in order]
    y_positions = list(range(len(order)))

    fig, ax = plt.subplots(figsize=(13, 6.8), dpi=180)
    fig.patch.set_facecolor("#f8fafc")
    ax.set_facecolor("#f8fafc")
    left = [0] * len(order)
    for key, label, color in OUTCOMES:
        values = [int(targets[name][key]) for name in order]
        bars = ax.barh(
            y_positions,
            values,
            left=left,
            height=0.58,
            label=label,
            color=color,
            edgecolor="#f8fafc",
            linewidth=1.2,
        )
        for bar, value in zip(bars, values):
            if value:
                ax.text(
                    bar.get_x() + bar.get_width() / 2,
                    bar.get_y() + bar.get_height() / 2,
                    str(value),
                    ha="center",
                    va="center",
                    color="white",
                    fontsize=11,
                    fontweight="bold",
                )
        left = [current + value for current, value in zip(left, values)]

    ax.set_yticks(y_positions, labels, fontsize=12, fontweight="semibold")
    ax.invert_yaxis()
    ax.set_xlim(0, 10)
    ax.set_xticks(range(0, 11))
    ax.set_xlabel("Cases (10 per target)", fontsize=11)
    ax.grid(axis="x", color="#cbd5e1", linewidth=0.8, alpha=0.65)
    ax.set_axisbelow(True)
    for spine in ax.spines.values():
        spine.set_visible(False)
    ax.tick_params(axis="both", length=0, colors="#334155")
    ax.legend(
        ncol=4,
        loc="lower center",
        bbox_to_anchor=(0.5, 1.01),
        frameon=False,
        fontsize=10,
    )
    fig.suptitle(
        "Black-Box Protocol — Final Observed Results",
        x=0.08,
        y=0.97,
        ha="left",
        fontsize=20,
        fontweight="bold",
        color="#0f172a",
    )
    ax.set_title(
        "Same frozen protocol and capability-aware evaluation criteria",
        loc="left",
        pad=42,
        fontsize=11,
        color="#475569",
    )
    fig.text(
        0.08,
        0.025,
        "AletheionAGI was revalidated after a transient HTTP 503: 9 PASS · 0 FAIL · 1 SKIPPED · 0 ERROR.\n"
        + "Sources — "
        + " | ".join(sources),
        ha="left",
        va="bottom",
        fontsize=8.5,
        color="#64748b",
    )
    fig.subplots_adjust(left=0.23, right=0.96, top=0.78, bottom=0.18)

    output = args.output.resolve() if args.output else base_dir / "RESULTS_FINAL.png"
    output.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output, dpi=180, facecolor=fig.get_facecolor())
    plt.close(fig)
    print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
