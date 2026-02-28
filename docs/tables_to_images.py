#!/usr/bin/env python3
"""Convert markdown tables in blog-post.md to PNG images."""

import re
import textwrap
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np


OUTPUT_DIR = Path(__file__).parent / "table_images"
OUTPUT_DIR.mkdir(exist_ok=True)

BLOG = (Path(__file__).parent / "blog-post.md").read_text()


def parse_md_table(text: str):
    """Parse a markdown table into headers and rows."""
    lines = [l.strip() for l in text.strip().splitlines() if l.strip()]
    headers = [c.strip().replace("**", "") for c in lines[0].split("|")[1:-1]]
    rows = []
    for line in lines[2:]:  # skip header and separator
        cells = [c.strip() for c in line.split("|")[1:-1]]
        rows.append(cells)
    return headers, rows


def find_tables(md_text: str):
    """Find all markdown tables and return (start_pos, end_pos, table_text)."""
    tables = []
    lines = md_text.split("\n")
    i = 0
    while i < len(lines):
        if (lines[i].strip().startswith("|")
            and i + 1 < len(lines)
            and re.match(r"^\s*\|[-:\s|]+\|\s*$", lines[i + 1])):
            start = i
            end = i
            while end < len(lines) and lines[end].strip().startswith("|"):
                end += 1
            table_text = "\n".join(lines[start:end])
            tables.append((start, end, table_text))
            i = end
        else:
            i += 1
    return tables


def clean_cell(text: str) -> str:
    """Remove markdown bold markers for display."""
    return text.replace("**", "").strip()


def wrap_cell_text(text: str, width: int) -> str:
    """Wrap text to fit within a cell."""
    if len(text) <= width:
        return text
    return "\n".join(textwrap.wrap(text, width=width))


def strip_md_links(text: str) -> str:
    """Convert [text](url) markdown links to just text."""
    return re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)


def render_table(headers, rows, filename, title=None, col_widths=None,
                 fontsize=9, figscale=1.0, wrap_widths=None,
                 left_align_cols=None):
    """Render a table as a PNG image.

    wrap_widths: dict mapping column index to wrap character width
    left_align_cols: set of column indices to left-align (default: col 0 and long-text cols)
    """
    clean_headers = [clean_cell(h) for h in headers]
    clean_rows = [[clean_cell(c) for c in row] for row in rows]

    # Strip markdown links from cells
    clean_rows = [[strip_md_links(c) for c in row] for row in clean_rows]

    n_cols = len(clean_headers)
    n_rows = len(clean_rows)

    # Apply text wrapping if specified
    max_lines_per_row = [1] * n_rows
    if wrap_widths:
        for i, row in enumerate(clean_rows):
            for j, cell in enumerate(row):
                if j in wrap_widths:
                    wrapped = wrap_cell_text(cell, wrap_widths[j])
                    clean_rows[i][j] = wrapped
                    lines_in_cell = wrapped.count("\n") + 1
                    max_lines_per_row[i] = max(max_lines_per_row[i], lines_in_cell)

    # Estimate column widths based on content
    if col_widths is None:
        col_widths = []
        for j in range(n_cols):
            # For wrapped text, use the wrap width; otherwise measure content
            if wrap_widths and j in wrap_widths:
                max_len = wrap_widths[j]
            else:
                max_len = len(clean_headers[j])
                for row in clean_rows:
                    if j < len(row):
                        # For multiline cells, measure the longest line
                        for line in row[j].split("\n"):
                            max_len = max(max_len, len(line))
            col_widths.append(max(0.06, max_len * 0.011))
        total = sum(col_widths)
        col_widths = [w / total for w in col_widths]

    # Determine left-aligned columns
    if left_align_cols is None:
        left_align_cols = {0}
        for j in range(n_cols):
            for row in clean_rows:
                if j < len(row) and len(row[j]) > 25:
                    left_align_cols.add(j)

    # Calculate figure dimensions
    base_row_height = 0.35
    fig_width = max(8, n_cols * 1.4) * figscale
    total_row_units = sum(max(1, ml * 0.8) for ml in max_lines_per_row)
    fig_height = max(2.0, (total_row_units + 1.5) * base_row_height + 0.8) * figscale

    fig, ax = plt.subplots(figsize=(fig_width, fig_height))
    ax.axis("off")

    table = ax.table(
        cellText=clean_rows,
        colLabels=clean_headers,
        cellLoc="center",
        loc="center",
        colWidths=col_widths,
    )

    table.auto_set_font_size(False)
    table.set_fontsize(fontsize)

    # Row height calculation
    base_h = 1.0 / (n_rows + 1.5)

    # Style header
    for j in range(n_cols):
        cell = table[0, j]
        cell.set_facecolor("#2c3e50")
        cell.set_text_props(color="white", fontweight="bold", fontsize=fontsize)
        cell.set_height(base_h * 1.2)
        cell.set_edgecolor("#bdc3c7")
        if j in left_align_cols:
            cell._loc = "left"
            cell.set_text_props(ha="left", color="white", fontweight="bold",
                                fontsize=fontsize)

    # Style data rows
    for i in range(1, n_rows + 1):
        row_lines = max_lines_per_row[i - 1]
        row_h = base_h * max(1.0, row_lines * 0.85)
        for j in range(n_cols):
            cell = table[i, j]
            cell.set_edgecolor("#bdc3c7")
            cell.set_height(row_h)

            # Alternating row colors
            if i % 2 == 0:
                cell.set_facecolor("#f8f9fa")
            else:
                cell.set_facecolor("#ffffff")

            # Color-code ALLOW/WARN/BLOCK cells
            text = clean_rows[i - 1][j] if j < len(clean_rows[i - 1]) else ""
            if text == "ALLOW":
                cell.set_facecolor("#d4edda")
                cell.set_text_props(color="#155724", fontweight="bold")
            elif text == "WARN":
                cell.set_facecolor("#fff3cd")
                cell.set_text_props(color="#856404", fontweight="bold")
            elif text == "BLOCK":
                cell.set_facecolor("#f8d7da")
                cell.set_text_props(color="#721c24", fontweight="bold")

            # Left-align specified columns
            if j in left_align_cols:
                cell._loc = "left"
                # Preserve color-coding text props if already set
                if text not in ("ALLOW", "WARN", "BLOCK"):
                    cell.set_text_props(ha="left")

    if title:
        fig.suptitle(title, fontsize=fontsize + 2, fontweight="bold", y=0.98)

    plt.tight_layout()
    out_path = OUTPUT_DIR / filename
    fig.savefig(out_path, dpi=200, bbox_inches="tight", pad_inches=0.15,
                facecolor="white", edgecolor="none")
    plt.close(fig)
    print(f"  Saved: {out_path}")
    return out_path


# ── Find all tables and render them ──────────────────────────────────────────

tables = find_tables(BLOG)
print(f"Found {len(tables)} tables\n")

# Table-specific configs
table_configs = [
    {  # Table 1: Malicious error distribution
        "filename": "table_b1_malicious_errors.png",
        "title": "Error Distribution — Malicious (GTFOBins) Dataset",
        "figscale": 1.1,
        "fontsize": 9,
    },
    {  # Table 2: Harmless error distribution
        "filename": "table_b2_harmless_errors.png",
        "title": "Error Distribution — Harmless Dataset",
        "figscale": 1.0,
        "fontsize": 9,
    },
    {  # Table 3: Cost comparison
        "filename": "table_c_cost.png",
        "title": "Cost Comparison",
        "figscale": 1.0,
        "fontsize": 9,
    },
    {  # Table 4: Category difficulty
        "filename": "table_d_category_difficulty.png",
        "title": "Per-Category Difficulty",
        "figscale": 1.0,
        "fontsize": 9,
    },
    {  # Table 5: Excluded categories (long text in col 1)
        "filename": "table_e1_excluded_categories.png",
        "title": "Excluded GTFOBins Categories",
        "figscale": 1.2,
        "fontsize": 8,
        "wrap_widths": {1: 70},
        "left_align_cols": {0, 1},
    },
    {  # Table 6: Category distribution
        "filename": "table_e2_category_distribution.png",
        "title": "GTFOBins Category Distribution",
        "figscale": 0.9,
        "fontsize": 9,
    },
    {  # Table 7: Mislabeled commands (long text in cols 0, 2)
        "filename": "table_f1_mislabeled_commands.png",
        "title": "Mislabeled Package-Installation Commands",
        "figscale": 1.2,
        "fontsize": 8,
        "left_align_cols": {0, 2},
    },
    {  # Table 8: Model classifications (ALLOW/WARN/BLOCK grid)
        "filename": "table_f2_model_classifications.png",
        "title": "How Models Classified Package-Installation Commands",
        "figscale": 1.3,
        "fontsize": 8,
    },
    {  # Table 9: Latency dissection (small table)
        "filename": "table_g_latency.png",
        "title": "Gemini 3 Flash Latency Dissection",
        "figscale": 1.0,
        "fontsize": 10,
        "left_align_cols": {0},
    },
    {  # Table 10: Models tested (long text, links in cols 0, 1, 2)
        "filename": "table_n_models.png",
        "title": "Models Tested",
        "figscale": 2.5,
        "fontsize": 10,
        "wrap_widths": {1: 35, 2: 45},
        "left_align_cols": {0, 1, 2},
    },
]

lines = BLOG.split("\n")
replacements = []

for idx, (start, end, table_text) in enumerate(tables):
    config = table_configs[idx] if idx < len(table_configs) else {
        "filename": f"table_{idx + 1}.png",
        "title": None,
        "figscale": 1.0,
        "fontsize": 9,
    }
    print(f"Table {idx + 1} (lines {start + 1}–{end}): {config['filename']}")
    headers, rows = parse_md_table(table_text)
    render_table(
        headers, rows,
        filename=config["filename"],
        title=config.get("title"),
        figscale=config.get("figscale", 1.0),
        fontsize=config.get("fontsize", 9),
        wrap_widths=config.get("wrap_widths"),
        left_align_cols=config.get("left_align_cols"),
    )
    replacements.append((start, end, config["filename"]))

# ── Replace tables in markdown with image references ─────────────────────────

print("\nGenerating updated blog post...")
new_lines = []
skip_until = -1
for i, line in enumerate(lines):
    if i < skip_until:
        continue
    replaced = False
    for start, end, filename in replacements:
        if i == start:
            new_lines.append(f"![{filename.replace('.png', '').replace('_', ' ').title()}](table_images/{filename})")
            new_lines.append("")
            skip_until = end
            replaced = True
            break
    if not replaced:
        new_lines.append(line)

out_path = Path(__file__).parent / "blog-post-with-images.md"
out_path.write_text("\n".join(new_lines))
print(f"Written: {out_path}")
print("Done!")
