"""文档解析服务：支持 PDF / Word / Excel / Markdown / HTML / 纯文本

PDF 解析采用 pdfplumber 提取表格并转为结构化自然语言文本，
确保表格中的键值关系（如 产品编号→冲刀型号）在后续分块和检索中不丢失。
"""

import hashlib
import re
from pathlib import Path

import fitz  # PyMuPDF（回退方案）
import pdfplumber
from docx import Document as DocxDocument


def compute_file_hash(file_path: str) -> str:
    h = hashlib.sha256()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def get_file_format(file_name: str) -> str:
    ext = Path(file_name).suffix.lower().lstrip(".")
    return ext or "unknown"


def _is_meaningful_header(headers: list[str]) -> bool:
    """判断表头是否有效（非空、非纯数字、有实际含义）"""
    meaningful = 0
    for h in headers:
        h = h.strip()
        if not h:
            continue
        # 纯数字或纯符号不算有效表头
        if re.match(r'^[\d\.\,\-\+\s]+$', h):
            continue
        meaningful += 1
    return meaningful >= 1


def _has_usable_headers(headers: list[str]) -> bool:
    """判断表头是否可用（需要有足够比例的非空列）"""
    total = len(headers)
    if total == 0:
        return False
    non_empty = sum(1 for h in headers if h.strip())
    # 至少 25% 的列有表头，且不少于 2 列
    return non_empty >= 2 and non_empty / total >= 0.25


def _strip_repeated_prefix(rows: list[str]) -> list[str]:
    """去掉因 pdfplumber 合并单元格导致的每行重复前缀

    找出所有行共享的最长公共前缀，如果长度 > 5 个字符则去掉。
    这对于处理跨行合并单元格（如提示文字）非常有效。
    """
    if len(rows) < 2:
        return rows

    # 找出所有行的最长公共前缀
    def _common_prefix(a: str, b: str) -> str:
        min_len = min(len(a), len(b))
        for i in range(min_len):
            if a[i] != b[i]:
                return a[:i]
        return a[:min_len]

    common = rows[0]
    for row in rows[1:]:
        common = _common_prefix(common, row)
        if not common:
            break

    # 只去掉足够长且以标点结尾的前缀（避免去掉有意义的内容）
    if len(common) > 5:
        # 回退到最近的标点/空白位置，确保不切断有意义内容
        cut_at = len(common)
        for sep in ("，", "。", "；", "、", "：", " ", "\n"):
            pos = common.rfind(sep)
            if pos > 5:
                cut_at = pos + 1
                break
        common = common[:cut_at]

    if len(common) >= 5:
        stripped = []
        for row in rows:
            if row.startswith(common):
                row = row[len(common):].lstrip("，、。； ")
            stripped.append(row)
        return stripped

    return rows


def parse_pdf(file_path: str) -> list[dict]:
    """解析 PDF，提取表格并转为结构化自然语言文本

    处理两类表格：
    1. 标准表格（有清晰表头）→ "列名：值" 键值对格式
    2. 非标准表格（复杂布局/合并单元格）→ 直接拼接每行所有值

    同时提取普通文本。pdfplumber 失败时回退到 PyMuPDF。
    """
    pages = []

    with pdfplumber.open(file_path) as pdf:
        for i, page in enumerate(pdf.pages):
            page_num = i + 1
            content_parts = []

            # ---- 第 1 步：提取表格并转为结构化文本 ----
            tables = page.extract_tables()
            table_rows: list[str] = []

            if tables:
                for table in tables:
                    if not table or len(table) < 2:
                        continue

                    raw_headers = [str(h).strip() if h else "" for h in table[0]]
                    use_headers = _has_usable_headers(raw_headers)

                    for row in table[1:]:
                        if not row or all(
                            cell is None or str(cell).strip() == ""
                            for cell in row
                        ):
                            continue

                        if use_headers:
                            # 标准模式：表头：值
                            parts = []
                            for j, cell in enumerate(row):
                                cell_text = str(cell).strip() if cell else ""
                                if not cell_text:
                                    continue
                                if j < len(raw_headers) and raw_headers[j]:
                                    parts.append(f"{raw_headers[j]}：{cell_text}")
                                else:
                                    parts.append(cell_text)
                            if parts:
                                table_rows.append("，".join(parts))
                        else:
                            # 非标准模式：直接拼接所有非空值
                            cells = [
                                str(c).strip()
                                for c in row
                                if c is not None and str(c).strip()
                            ]
                            if cells:
                                table_rows.append("，".join(cells))

                if table_rows:
                    # 去掉重复的合并单元格前缀
                    table_rows = _strip_repeated_prefix(table_rows)
                    content_parts.append("\n".join(table_rows))

            # ---- 第 2 步：提取非表格的普通文本 ----
            text = page.extract_text()
            if text and text.strip():
                content_parts.append(text.strip())

            # ---- 第 3 步：合并输出 ----
            if content_parts:
                full_content = "\n\n".join(content_parts)
                if full_content.strip():
                    pages.append({
                        "page_num": page_num,
                        "content": full_content,
                        "section_title": None,
                    })

    # ---- 回退方案：pdfplumber 未提取到任何内容时用 PyMuPDF ----
    if not pages:
        pages = _parse_pdf_fitz(file_path)

    return pages


def _parse_pdf_fitz(file_path: str) -> list[dict]:
    """PyMuPDF 回退解析（无表格识别能力，仅提取纯文本）"""
    pages = []
    with fitz.open(file_path) as doc:
        for i, page in enumerate(doc):
            text = page.get_text("text").strip()
            if text:
                pages.append({
                    "page_num": i + 1,
                    "content": text,
                    "section_title": None,
                })
    return pages


def parse_docx(file_path: str) -> list[dict]:
    """解析 Word 文档"""
    doc = DocxDocument(file_path)
    pages = []
    current_section = None
    content_parts = []

    for para in doc.paragraphs:
        text = para.text.strip()
        if not text:
            continue
        if para.style.name.startswith("Heading"):
            if content_parts:
                pages.append({
                    "page_num": 1,
                    "content": "\n".join(content_parts),
                    "section_title": current_section,
                })
                content_parts = []
            current_section = text
        else:
            content_parts.append(text)

    if content_parts:
        pages.append({
            "page_num": 1,
            "content": "\n".join(content_parts),
            "section_title": current_section,
        })

    return pages


def parse_markdown(file_path: str) -> list[dict]:
    """解析 Markdown，按标题分块"""
    with open(file_path, "r", encoding="utf-8") as f:
        content = f.read()

    lines = content.split("\n")
    pages = []
    current_section = None
    current_lines = []

    for line in lines:
        stripped = line.strip()
        if stripped.startswith("#"):
            if current_lines:
                pages.append({
                    "page_num": 1,
                    "content": "\n".join(current_lines).strip(),
                    "section_title": current_section,
                })
                current_lines = []
            current_section = stripped.lstrip("#").strip()
        else:
            current_lines.append(line)

    if current_lines:
        pages.append({
            "page_num": 1,
            "content": "\n".join(current_lines).strip(),
            "section_title": current_section,
        })

    if not pages and content.strip():
        pages.append({"page_num": 1, "content": content.strip(), "section_title": None})

    return pages


def parse_txt(file_path: str) -> list[dict]:
    """解析纯文本文件"""
    with open(file_path, "r", encoding="utf-8") as f:
        content = f.read()
    if not content.strip():
        return []
    return [{"page_num": 1, "content": content.strip(), "section_title": None}]


def parse_html(file_path: str) -> list[dict]:
    """解析 HTML 文件"""
    from bs4 import BeautifulSoup

    with open(file_path, "r", encoding="utf-8") as f:
        soup = BeautifulSoup(f.read(), "html.parser")

    for tag in soup(["script", "style", "nav", "footer", "header"]):
        tag.decompose()

    text = soup.get_text(separator="\n", strip=True)
    if not text:
        return []

    title = soup.title.string.strip() if soup.title and soup.title.string else None
    return [{"page_num": 1, "content": text, "section_title": title}]


def parse_document(file_path: str, file_format: str) -> list[dict]:
    """根据格式解析文档，返回 [{page_num, content, section_title}]"""
    parsers = {
        "pdf": parse_pdf,
        "docx": parse_docx,
        "doc": parse_docx,
        "md": parse_markdown,
        "markdown": parse_markdown,
        "txt": parse_txt,
        "html": parse_html,
        "htm": parse_html,
    }

    parser = parsers.get(file_format)
    if parser is None:
        raise ValueError(f"不支持的文件格式: {file_format}")

    return parser(file_path)
