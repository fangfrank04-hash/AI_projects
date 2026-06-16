"""
HTML Table to Markdown converter using 2D matrix flattening algorithm.
Handles colspan, rowspan, and caption in complex merged-cell tables.
"""

from bs4 import BeautifulSoup, Tag


def parse_html_table_to_md(html_string: str) -> str:
    soup = BeautifulSoup(html_string, "html.parser")

    for table in soup.find_all("table"):
        md_table = _convert_table_to_md(table)
        table.replace_with(soup.new_string(md_table))

    return str(soup)


def _convert_table_to_md(table: Tag) -> str:
    # 1. Pre-scan: calculate max_cols
    rows = table.find_all("tr")
    max_cols = 0
    for tr in rows:
        col_count = 0
        for cell in tr.find_all(["th", "td"]):
            colspan = int(cell.get("colspan", 1))
            col_count += colspan
        if col_count > max_cols:
            max_cols = col_count

    num_rows = len(rows)
    grid = [["" for _ in range(max_cols)] for _ in range(num_rows)]
    # Track which cells are occupied by rowspan from above
    occupied = [[False for _ in range(max_cols)] for _ in range(num_rows)]

    # 2. Fill grid with flattening
    for row_idx, tr in enumerate(rows):
        col_idx = 0
        for cell in tr.find_all(["th", "td"]):
            # Skip columns already occupied by rowspan from above
            while col_idx < max_cols and occupied[row_idx][col_idx]:
                col_idx += 1

            if col_idx >= max_cols:
                break

            colspan = int(cell.get("colspan", 1))
            rowspan = int(cell.get("rowspan", 1))

            # 3. Safe text extraction
            text = cell.get_text(strip=True)
            text = text.replace("\n", " ").replace("\r", " ")
            text = text.replace("|", "&#124;")

            # 4. Flatten content across all covered cells
            for dr in range(rowspan):
                r = row_idx + dr
                if r >= num_rows:
                    break
                for dc in range(colspan):
                    c = col_idx + dc
                    if c >= max_cols:
                        break
                    grid[r][c] = text
                    if dr > 0 or dc > 0:
                        pass  # text already set, mark occupied
                    if dr > 0:
                        occupied[r][c] = True

            col_idx += colspan

    # 5. Build Markdown output
    lines = []

    # Caption support
    caption = table.find("caption")
    if caption:
        caption_text = caption.get_text(strip=True)
        lines.append(f"**{caption_text}**")
        lines.append("")

    # Write grid rows
    for row_idx in range(num_rows):
        md_row = "| " + " | ".join(grid[row_idx]) + " |"
        lines.append(md_row)

        # Separator line after first row (table header)
        if row_idx == 0:
            sep = "| " + " | ".join(["---"] * max_cols) + " |"
            lines.append(sep)

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    test_html = (
        '<p>这是前置文本内容，不应被修改。</p>\n'
        '<table>\n'
        '    <caption>产品收费标准说明</caption>\n'
        '    <tr>\n'
        '        <th>费用名称</th>\n'
        '        <th>收费对象</th>\n'
        '        <th>收费费率</th>\n'
        '    </tr>\n'
        '    <tr>\n'
        '        <td rowspan="2">发行登记服务费</td>\n'
        '        <td>甲类机构</td>\n'
        '        <td>0.01%</td>\n'
        '    </tr>\n'
        '    <tr>\n'
        '        <td>乙类机构</td>\n'
        '        <td>0.02%</td>\n'
        '    </tr>\n'
        '    <tr>\n'
        '        <td>账户维护费</td>\n'
        '        <td colspan="2">全量客户统一收取 500元/年</td>\n'
        '    </tr>\n'
        '</table>\n'
        '<p>这是后置文本内容，不应被修改。</p>'
    )

    print("=" * 60)
    print("原始 HTML:")
    print("=" * 60)
    print(test_html)

    result = parse_html_table_to_md(test_html)

    print()
    print("=" * 60)
    print("转换后:")
    print("=" * 60)
    print(result)

    # ------------------------------------------------------------------
    # Additional test: verify no misalignment with pipe characters
    # ------------------------------------------------------------------
    print()
    print("=" * 60)
    print("边界测试 — 包含 | 竖线的单元格:")
    print("=" * 60)

    pipe_html = (
        "<table>"
        "<tr><th>A</th><th>B</th></tr>"
        "<tr><td>x|y</td><td>z</td></tr>"
        "</table>"
    )
    print("输入:", pipe_html)
    print("输出:")
    print(parse_html_table_to_md(pipe_html))

    # ------------------------------------------------------------------
    # Additional test: complex rowspan + colspan overlap
    # ------------------------------------------------------------------
    print()
    print("=" * 60)
    print("边界测试 — 复杂 rowspan + colspan 交叠:")
    print("=" * 60)

    complex_html = (
        "<table>"
        "<caption>复杂合并测试</caption>"
        "<tr><th colspan=\"2\">头部A</th><th>头部B</th></tr>"
        "<tr><td rowspan=\"2\">跨行1</td><td>单元格1</td><td>单元格2</td></tr>"
        "<tr><td colspan=\"2\">跨列+跨行占位</td></tr>"
        "<tr><td colspan=\"3\">全行合并</td></tr>"
        "</table>"
    )
    print("输入:", complex_html)
    print("输出:")
    print(parse_html_table_to_md(complex_html))
