"""
Based on:
- https://github.com/anomalyco/opencode/blob/dev/packages/opencode/src/tool/edit.ts
"""

from __future__ import annotations

import difflib
import json
import re
from collections.abc import Generator
from dataclasses import dataclass
from pathlib import Path
from typing import (
    Callable,
    NotRequired,
    TypedDict,
)

from app.tool import Tool

MAX_DIAGNOSTICS_PER_FILE = 20

# Similarity thresholds for block anchor fallback matching
SINGLE_CANDIDATE_SIMILARITY_THRESHOLD = 0.0
MULTIPLE_CANDIDATES_SIMILARITY_THRESHOLD = 0.3


def normalize_line_endings(text: str) -> str:
    return text.replace("\r\n", "\n")


def create_two_files_patch(file_path: str, old_text: str, new_text: str) -> str:
    """
    Rough equivalent of diff.createTwoFilesPatch(...), using a unified diff.
    """
    old_lines = normalize_line_endings(old_text).splitlines(True)
    new_lines = normalize_line_endings(new_text).splitlines(True)

    diff_iter = difflib.unified_diff(
        old_lines,
        new_lines,
        fromfile=file_path,
        tofile=file_path,
        lineterm="",
    )
    return "\n".join(diff_iter)


def count_line_additions_deletions(old_text: str, new_text: str) -> tuple[int, int]:
    """
    Rough equivalent of diff.diffLines(...) counts (line-based).
    """
    old_lines = normalize_line_endings(old_text).splitlines()
    new_lines = normalize_line_endings(new_text).splitlines()

    additions = 0
    deletions = 0
    for line in difflib.ndiff(old_lines, new_lines):
        if line.startswith("+ "):
            additions += 1
        elif line.startswith("- "):
            deletions += 1
    return additions, deletions


def levenshtein(a: str, b: str) -> int:
    """
    Levenshtein distance algorithm implementation.
    """
    if a == "" or b == "":
        return max(len(a), len(b))

    rows = len(a) + 1
    cols = len(b) + 1
    matrix: list[list[int]] = [[0] * cols for _ in range(rows)]

    for i in range(rows):
        matrix[i][0] = i
    for j in range(cols):
        matrix[0][j] = j

    for i in range(1, rows):
        for j in range(1, cols):
            cost = 0 if a[i - 1] == b[j - 1] else 1
            matrix[i][j] = min(
                matrix[i - 1][j] + 1,  # deletion
                matrix[i][j - 1] + 1,  # insertion
                matrix[i - 1][j - 1] + cost,  # substitution
            )

    return matrix[len(a)][len(b)]


Replacer = Callable[[str, str], Generator[str, None, None]]


def simple_replacer(_content: str, find: str) -> Generator[str, None, None]:
    yield find


def line_trimmed_replacer(content: str, find: str) -> Generator[str, None, None]:
    original_lines = content.split("\n")
    search_lines = find.split("\n")

    if search_lines and search_lines[-1] == "":
        search_lines.pop()

    if not search_lines:
        return

    for i in range(0, len(original_lines) - len(search_lines) + 1):
        matches = True
        for j in range(len(search_lines)):
            if original_lines[i + j].strip() != search_lines[j].strip():
                matches = False
                break

        if matches:
            match_start_index = sum(
                len(original_lines[k]) + 1 for k in range(i)
            )  # +1 for '\n'
            match_end_index = match_start_index
            for k in range(len(search_lines)):
                match_end_index += len(original_lines[i + k])
                if k < len(search_lines) - 1:
                    match_end_index += 1
            yield content[match_start_index:match_end_index]


def block_anchor_replacer(content: str, find: str) -> Generator[str, None, None]:
    original_lines = content.split("\n")
    search_lines = find.split("\n")

    if len(search_lines) < 3:
        return

    if search_lines and search_lines[-1] == "":
        search_lines.pop()

    first_line_search = search_lines[0].strip()
    last_line_search = search_lines[-1].strip()
    search_block_size = len(search_lines)

    candidates: list[dict[str, int]] = []
    for i in range(len(original_lines)):
        if original_lines[i].strip() != first_line_search:
            continue
        for j in range(i + 2, len(original_lines)):
            if original_lines[j].strip() == last_line_search:
                candidates.append({"start_line": i, "end_line": j})
                break

    if not candidates:
        return

    def emit_block(start_line: int, end_line: int) -> Generator[str, None, None]:
        match_start_index = sum(len(original_lines[k]) + 1 for k in range(start_line))
        match_end_index = match_start_index
        for k in range(start_line, end_line + 1):
            match_end_index += len(original_lines[k])
            if k < end_line:
                match_end_index += 1
        yield content[match_start_index:match_end_index]

    if len(candidates) == 1:
        start_line = candidates[0]["start_line"]
        end_line = candidates[0]["end_line"]
        actual_block_size = end_line - start_line + 1

        similarity = 0.0
        lines_to_check = min(search_block_size - 2, actual_block_size - 2)

        if lines_to_check > 0:
            for j in range(1, min(search_block_size - 1, actual_block_size - 1)):
                original_line = original_lines[start_line + j].strip()
                search_line = search_lines[j].strip()
                max_len = max(len(original_line), len(search_line))
                if max_len == 0:
                    continue
                distance = levenshtein(original_line, search_line)
                similarity += (1 - distance / max_len) / lines_to_check
                if similarity >= SINGLE_CANDIDATE_SIMILARITY_THRESHOLD:
                    break
        else:
            similarity = 1.0

        if similarity >= SINGLE_CANDIDATE_SIMILARITY_THRESHOLD:
            yield from emit_block(start_line, end_line)
        return

    best_match: dict[str, int] | None = None
    max_similarity = -1.0

    for cand in candidates:
        start_line = cand["start_line"]
        end_line = cand["end_line"]
        actual_block_size = end_line - start_line + 1

        similarity = 0.0
        lines_to_check = min(search_block_size - 2, actual_block_size - 2)

        if lines_to_check > 0:
            for j in range(1, min(search_block_size - 1, actual_block_size - 1)):
                original_line = original_lines[start_line + j].strip()
                search_line = search_lines[j].strip()
                max_len = max(len(original_line), len(search_line))
                if max_len == 0:
                    continue
                distance = levenshtein(original_line, search_line)
                similarity += 1 - distance / max_len
            similarity /= lines_to_check
        else:
            similarity = 1.0

        if similarity > max_similarity:
            max_similarity = similarity
            best_match = cand

    if best_match and max_similarity >= MULTIPLE_CANDIDATES_SIMILARITY_THRESHOLD:
        yield from emit_block(best_match["start_line"], best_match["end_line"])


def whitespace_normalized_replacer(
    content: str, find: str
) -> Generator[str, None, None]:
    def normalize_whitespace(text: str) -> str:
        return re.sub(r"\s+", " ", text).strip()

    normalized_find = normalize_whitespace(find)

    lines = content.split("\n")
    for line in lines:
        if normalize_whitespace(line) == normalized_find:
            yield line
            continue

        normalized_line = normalize_whitespace(line)
        if normalized_find and normalized_find in normalized_line:
            words = find.strip().split()
            if words:
                pattern = r"\s+".join(re.escape(word) for word in words)
                try:
                    match = re.search(pattern, line)
                    if match:
                        yield match.group(0)
                except re.error:
                    pass

    find_lines = find.split("\n")
    if len(find_lines) > 1:
        for i in range(0, len(lines) - len(find_lines) + 1):
            block = "\n".join(lines[i : i + len(find_lines)])
            if normalize_whitespace(block) == normalized_find:
                yield block


def indentation_flexible_replacer(
    content: str, find: str
) -> Generator[str, None, None]:
    def remove_indentation(text: str) -> str:
        lines = text.split("\n")
        non_empty = [line for line in lines if line.strip()]
        if not non_empty:
            return text

        min_indent = min(len(re.match(r"^(\s*)", line).group(1)) for line in non_empty)  # type: ignore[union-attr]
        return "\n".join(
            line if not line.strip() else line[min_indent:] for line in lines
        )

    normalized_find = remove_indentation(find)

    content_lines = content.split("\n")
    find_lines = find.split("\n")

    for i in range(0, len(content_lines) - len(find_lines) + 1):
        block = "\n".join(content_lines[i : i + len(find_lines)])
        if remove_indentation(block) == normalized_find:
            yield block


def escape_normalized_replacer(content: str, find: str) -> Generator[str, None, None]:
    def unescape_string(s: str) -> str:
        def repl(match: re.Match[str]) -> str:
            ch = match.group(1)
            mapping = {
                "n": "\n",
                "t": "\t",
                "r": "\r",
                "'": "'",
                '"': '"',
                "`": "`",
                "\\": "\\",
                "\n": "\n",
                "$": "$",
            }
            return mapping.get(ch, match.group(0))

        return re.sub(r"\\(n|t|r|'|\"|`|\\|\n|\$)", repl, s)

    unescaped_find = unescape_string(find)

    if unescaped_find and unescaped_find in content:
        yield unescaped_find

    lines = content.split("\n")
    find_lines = unescaped_find.split("\n")
    if not find_lines:
        return

    for i in range(0, len(lines) - len(find_lines) + 1):
        block = "\n".join(lines[i : i + len(find_lines)])
        unescaped_block = unescape_string(block)
        if unescaped_block == unescaped_find:
            yield block


def multi_occurrence_replacer(content: str, find: str) -> Generator[str, None, None]:
    start_index = 0
    while True:
        idx = content.find(find, start_index)
        if idx == -1:
            break
        yield find
        start_index = idx + len(find)


def trimmed_boundary_replacer(content: str, find: str) -> Generator[str, None, None]:
    trimmed_find = find.strip()
    if trimmed_find == find:
        return

    if trimmed_find and trimmed_find in content:
        yield trimmed_find

    lines = content.split("\n")
    find_lines = find.split("\n")
    if not find_lines:
        return

    for i in range(0, len(lines) - len(find_lines) + 1):
        block = "\n".join(lines[i : i + len(find_lines)])
        if block.strip() == trimmed_find:
            yield block


def context_aware_replacer(content: str, find: str) -> Generator[str, None, None]:
    find_lines = find.split("\n")
    if len(find_lines) < 3:
        return

    if find_lines and find_lines[-1] == "":
        find_lines.pop()

    content_lines = content.split("\n")
    first_line = find_lines[0].strip()
    last_line = find_lines[-1].strip()

    for i in range(len(content_lines)):
        if content_lines[i].strip() != first_line:
            continue

        for j in range(i + 2, len(content_lines)):
            if content_lines[j].strip() == last_line:
                block_lines = content_lines[i : j + 1]

                if len(block_lines) == len(find_lines):
                    matching_lines = 0
                    total_non_empty = 0

                    for k in range(1, len(block_lines) - 1):
                        block_line = block_lines[k].strip()
                        find_line = find_lines[k].strip()
                        if block_line or find_line:
                            total_non_empty += 1
                            if block_line == find_line:
                                matching_lines += 1

                    if (
                        total_non_empty == 0
                        or (matching_lines / total_non_empty) >= 0.5
                    ):
                        yield "\n".join(block_lines)
                        break
                break


def trim_diff(diff_text: str) -> str:
    lines = diff_text.split("\n")
    content_lines = [
        line
        for line in lines
        if (line.startswith("+") or line.startswith("-") or line.startswith(" "))
        and not line.startswith("---")
        and not line.startswith("+++")
    ]

    if not content_lines:
        return diff_text

    min_indent = float("inf")
    for line in content_lines:
        content = line[1:]
        if content.strip():
            m = re.match(r"^(\s*)", content)
            if m:
                min_indent = min(min_indent, len(m.group(1)))

    if min_indent == float("inf") or min_indent == 0:
        return diff_text

    trimmed_lines: list[str] = []
    for line in lines:
        if (
            (line.startswith("+") or line.startswith("-") or line.startswith(" "))
            and not line.startswith("---")
            and not line.startswith("+++")
        ):
            prefix = line[0]
            content = line[1:]
            trimmed_lines.append(prefix + content[int(min_indent) :])
        else:
            trimmed_lines.append(line)

    return "\n".join(trimmed_lines)


def replace(
    content: str, old_string: str, new_string: str, replace_all: bool = False
) -> str:
    if old_string == new_string:
        raise ValueError("oldString and newString must be different")

    not_found = True

    replacers: list[Replacer] = [
        simple_replacer,
        line_trimmed_replacer,
        block_anchor_replacer,
        whitespace_normalized_replacer,
        indentation_flexible_replacer,
        escape_normalized_replacer,
        trimmed_boundary_replacer,
        context_aware_replacer,
        multi_occurrence_replacer,
    ]

    for replacer in replacers:
        for search in replacer(content, old_string):
            idx = content.find(search)
            if idx == -1:
                continue

            not_found = False

            if replace_all:
                return content.replace(search, new_string)

            last_idx = content.rfind(search)
            if idx != last_idx:
                continue

            return content[:idx] + new_string + content[idx + len(search) :]

    if not_found:
        raise ValueError("oldString not found in content")

    raise ValueError(
        "Found multiple matches for oldString. Provide more surrounding lines in oldString to identify the correct match."
    )


@dataclass
class EditResult:
    path: str
    diff: str
    additions: int
    deletions: int


def edit_file_tool(
    *,
    path: str,
    old: str,
    new: str,
    replace_all: bool = False,
) -> str:
    """
    Minimal agent tool function:
    - If old == "": overwrite file with new (create dirs if needed).
    - Else: replace old -> new using heuristics (unique match unless replace_all=True).
    Returns diff + line stats.
    """
    if old == new:
        raise ValueError("old and new must be different")

    file_path = Path(path)

    before = ""
    if file_path.exists():
        if file_path.is_dir():
            raise IsADirectoryError("Target path is a directory")
        before = file_path.read_text(encoding="utf-8")

    if old == "":
        after = new
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_text(after, encoding="utf-8")
    else:
        if not file_path.exists():
            raise FileNotFoundError("File not found")
        after = replace(before, old, new, replace_all=replace_all)
        file_path.write_text(after, encoding="utf-8")

    # Re-read to match what is actually on disk
    after = file_path.read_text(encoding="utf-8")

    diff = trim_diff(create_two_files_patch(str(file_path), before, after))
    additions, deletions = count_line_additions_deletions(before, after)

    result = EditResult(
        path=path,
        diff=diff,
        additions=additions,
        deletions=deletions,
    )
    return json.dumps(
        {
            "path": result.path,
            "diff": result.diff,
            "additions": result.additions,
            "deletions": result.deletions,
        }
    )


description = """\
Performs exact string replacements in files. 

Usage:
- You must use your `Read` tool at least once in the conversation before editing. This tool will error if you attempt an edit without reading the file. 
- When editing text from Read tool output, ensure you preserve the exact indentation (tabs/spaces) as it appears AFTER the line number prefix. The line number prefix format is: spaces + line number + tab. Everything after that tab is the actual file content to match. Never include any part of the line number prefix in the oldString or newString.
- ALWAYS prefer editing existing files in the codebase. NEVER write new files unless explicitly required.
- Only use emojis if the user explicitly requests it. Avoid adding emojis to files unless asked.
- The edit will FAIL if `old_string` is not found in the file with an error "oldString not found in content".
- The edit will FAIL if `old_string` is found multiple times in the file with an error "oldString found multiple times and requires more code context to uniquely identify the intended match". Either provide a larger string with more surrounding context to make it unique or use `replaceAll` to change every instance of `oldString`. 
- Use `replace_all` for replacing and renaming strings across the file. This parameter is useful if you want to rename a variable for instance.
"""


class Args(TypedDict):
    filepath: str
    old_string: str
    new_string: str
    replace_all: NotRequired[bool]


class EditTool(Tool[Args]):
    description = description
    args_type = Args

    def __call__(self, args: Args):
        filepath = args["filepath"]
        old_string = args["old_string"]
        new_string = args["new_string"]
        replace_all = args.get("replace_all", False)
        output = edit_file_tool(
            path=filepath,
            old=old_string,
            new=new_string,
            replace_all=replace_all,
        )
        return output
