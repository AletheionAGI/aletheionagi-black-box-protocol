from __future__ import annotations

import argparse
import html
import json
from pathlib import Path

from _bootstrap import ROOT


COLORS = {
    "pass": "#16a34a",
    "fail": "#dc2626",
    "skipped": "#d97706",
    "errors": "#7c3aed",
}
LABELS = {"pass": "PASS", "fail": "FAIL", "skipped": "SKIPPED", "errors": "ERROR"}


def render(summary_path: Path, output_path: Path) -> None:
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    targets = summary["protocol_performance"]["targets"]
    names = list(targets)
    width, height = 1100, 540
    left, right, top, bottom = 220, 50, 105, 80
    chart_width = width - left - right
    row_height = (height - top - bottom) / max(len(names), 1)
    max_total = max(int(values["total_cases"]) for values in targets.values())
    scale = chart_width / max(max_total, 1)

    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        '<rect width="100%" height="100%" fill="#fafafa"/>',
        '<style>text{font-family:Inter,Arial,sans-serif;fill:#172033}.title{font-size:25px;font-weight:700}.sub{font-size:13px;fill:#5f6b7a}.name{font-size:15px;font-weight:600}.tick{font-size:12px;fill:#697586}.value{font-size:12px;font-weight:700;fill:white}</style>',
        '<text x="40" y="42" class="title">Black-Box Protocol — resultados por alvo</text>',
        f'<text x="40" y="68" class="sub">Fonte: {html.escape(str(summary_path.relative_to(ROOT)))}</text>',
    ]

    legend_x = left
    for key in ("pass", "fail", "skipped", "errors"):
        parts.append(f'<rect x="{legend_x}" y="82" width="14" height="14" rx="2" fill="{COLORS[key]}"/>')
        parts.append(f'<text x="{legend_x + 20}" y="94" class="tick">{LABELS[key]}</text>')
        legend_x += 115

    for tick in range(max_total + 1):
        x = left + tick * scale
        parts.append(f'<line x1="{x:.1f}" y1="{top}" x2="{x:.1f}" y2="{height-bottom}" stroke="#e4e7ec"/>')
        parts.append(f'<text x="{x:.1f}" y="{height-bottom+24}" text-anchor="middle" class="tick">{tick}</text>')

    for index, (name, values) in enumerate(targets.items()):
        y = top + index * row_height + row_height * 0.23
        bar_height = row_height * 0.54
        parts.append(f'<text x="{left-16}" y="{y+bar_height/2+5:.1f}" text-anchor="end" class="name">{html.escape(name)}</text>')
        x = left
        for key in ("pass", "fail", "skipped", "errors"):
            count = int(values[key])
            segment_width = count * scale
            if count:
                parts.append(f'<rect x="{x:.1f}" y="{y:.1f}" width="{segment_width:.1f}" height="{bar_height:.1f}" fill="{COLORS[key]}"/>')
                if segment_width >= 28:
                    parts.append(f'<text x="{x+segment_width/2:.1f}" y="{y+bar_height/2+4:.1f}" text-anchor="middle" class="value">{count}</text>')
            x += segment_width

    parts.append(f'<text x="{left+chart_width/2:.1f}" y="{height-18}" text-anchor="middle" class="sub">Quantidade de casos (10 por alvo)</text>')
    parts.append("</svg>")
    output_path.write_text("\n".join(parts) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate an SVG chart from a protocol summary")
    parser.add_argument("run_dir", type=Path, help="results/<timestamp> directory")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    run_dir = args.run_dir.resolve()
    output = args.output.resolve() if args.output else run_dir / "RESULTS.svg"
    render(run_dir / "summary.json", output)
    print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
