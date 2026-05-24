#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import re
from pathlib import Path
import pysubs2

# 半角片假名 Unicode 范围：U+FF61 ~ U+FF9F
_HALF_KANA_RE = re.compile(r"[\uff61-\uff9f]")

# 常规双引号与单引号（中英文）
_QUOTE_RE = re.compile(r"[\u0022\u201c\u201d\u0027\u2018\u2019]")

# 禁用标点与特殊符号（合并检查）：逗号、顿号、句号、波浪号、省略号、分隔号等
_BANNED_PUNCT_RE = re.compile(
    r"[\uff0c\u3001\u3002\uff0e,.\uff5e~"
    r"\u2026\u2025\u22ef\u22ee\u22f0\u22f1\ufe19"
    r"\u00b7\u30fb\u2022\u2027\u2219\u22c5\uff61\ufe52\uff65]|\.{3}"
)

# 慎用语气标点（需人工确认）：中文问号、英文问号、中文叹号、英文叹号
_CAUTION_PUNCT_RE = re.compile(r"[\uff1f?\uff01!]")

# 遗留标记：* # / 及其全角变体、反斜杠等译制辅助符号
_MARK_RE = re.compile(r"[*#/\\\uFF0A\uFF03\uFF0F\uFF3C]")


def _emit(result: str, results: list[str]) -> None:
    """同时打印并收集结果"""
    print(result)
    results.append(result)


def _format_timestamp(ms: int) -> str:
    """将毫秒统一格式化为 HH:MM:SS.cc"""
    total_seconds = ms // 1000
    hours = total_seconds // 3600
    minutes = (total_seconds % 3600) // 60
    seconds = total_seconds % 60
    centiseconds = (ms % 1000) // 10
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}.{centiseconds:02d}"


def check_char_format(file: Path, splitter: str = r"\N{\fnG-OTF Jo Shin Maru Go ProN M\fs45}", style: str = "Default") -> list[str]:
    """对 ASS 字幕进行字符格式静态检查，返回错误列表"""
    subs = pysubs2.load(str(file))
    results = []

    for line in subs:
        if line.is_comment or line.style != style:
            continue

        text = line.text
        if not text.strip():
            continue

        start_time = _format_timestamp(line.start)
        if splitter not in text:
            print(f"[格式] [{start_time}] 拆行失败 - 字幕行未找到中日文分隔符：{text}")
            continue
        chinese_raw, japanese_raw = text.split(splitter)

        # 检查日文原文开头/结尾的全角空格（会导致字幕移位无法居中）
        if japanese_raw.startswith("　"):
            _emit(
                f"[格式] [{start_time}] 开头全角空格 - "
                f"日文原文「{japanese_raw.strip()}」开头包含全角空格，会导致字幕移位无法居中，建议删除。",
                results,
            )
        if japanese_raw.endswith("　"):
            _emit(
                f"[格式] [{start_time}] 结尾全角空格 - "
                f"日文原文「{japanese_raw.strip()}」结尾包含全角空格，会导致字幕移位无法居中，建议删除。",
                results,
            )

        chinese = chinese_raw.strip()
        japanese = japanese_raw.strip()

        # 检查中文译文中的全角空格
        if "　" in chinese:
            _emit(
                f"[格式] [{start_time}] 全角空格 - "
                f"中文译文「{chinese}」中包含全角空格，建议替换为半角空格。",
                results,
            )

        # 检查中文译文中的禁用标点与特殊符号
        banned_found = _BANNED_PUNCT_RE.findall(chinese)
        if banned_found:
            banned_str = "".join(set(banned_found))
            _emit(
                f"[格式] [{start_time}] 禁用标点/特殊符号 - "
                f"中文译文「{chinese}」中包含禁用标点或特殊符号「{banned_str}」，要求删除（专有名词除外）。",
                results,
            )

        # 检查中文译文中的慎用语气标点（需人工确认）
        caution_found = _CAUTION_PUNCT_RE.findall(chinese)
        if caution_found:
            caution_str = "".join(set(caution_found))
            _emit(
                f"[格式] [{start_time}] 慎用语气标点 - "
                f"中文译文「{chinese}」中包含语气标点「{caution_str}」。"
                f"除非极度必要（观众完全听不出语气），否则建议删除；请人工确认是否有必要保留。",
                results,
            )

        # 检查中文译文中的遗留标记
        mark_found = _MARK_RE.findall(chinese)
        if mark_found:
            mark_str = "".join(set(mark_found))
            _emit(
                f"[格式] [{start_time}] 遗留标记 - "
                f"中文译文「{chinese}」中包含译制辅助标记「{mark_str}」，要求删除。",
                results,
            )

        # 检查中文译文中的常规引号
        quote_found = _QUOTE_RE.findall(chinese)
        if quote_found:
            quote_str = "".join(set(quote_found))
            _emit(
                f"[格式] [{start_time}] 引号格式 - "
                f"中文译文「{chinese}」中包含常规引号「{quote_str}」，建议替换为「」。",
                results,
            )

        # 检查日文原文中的半角空格（日文应使用全角空格）
        if " " in japanese:
            _emit(
                f"[格式] [{start_time}] 半角空格 - "
                f"日文原文「{japanese}」中包含半角空格，建议替换为全角空格（　）。",
                results,
            )

        # 检查日文原文开头/结尾的全角空格（会导致字幕移位无法居中）
        if japanese.startswith("　"):
            _emit(
                f"[格式] [{start_time}] 开头全角空格 - "
                f"日文原文「{japanese}」开头包含全角空格，会导致字幕移位无法居中，建议删除。",
                results,
            )
        if japanese.endswith("　"):
            _emit(
                f"[格式] [{start_time}] 结尾全角空格 - "
                f"日文原文「{japanese}」结尾包含全角空格，会导致字幕移位无法居中，建议删除。",
                results,
            )

        # 检查日文原文中的禁用标点与特殊符号
        banned_found = _BANNED_PUNCT_RE.findall(japanese)
        if banned_found:
            banned_str = "".join(set(banned_found))
            _emit(
                f"[格式] [{start_time}] 禁用标点/特殊符号 - "
                f"日文原文「{japanese}」中包含禁用标点或特殊符号「{banned_str}」，要求删除。",
                results,
            )

        # 检查日文原文中的慎用语气标点（需人工确认）
        caution_found = _CAUTION_PUNCT_RE.findall(japanese)
        if caution_found:
            caution_str = "".join(set(caution_found))
            _emit(
                f"[格式] [{start_time}] 慎用语气标点 - "
                f"日文原文「{japanese}」中包含语气标点「{caution_str}」。"
                f"除非极度必要（观众完全听不出语气），否则建议删除；请人工确认是否有必要保留。",
                results,
            )

        # 检查日文原文中的遗留标记
        mark_found = _MARK_RE.findall(japanese)
        if mark_found:
            mark_str = "".join(set(mark_found))
            _emit(
                f"[格式] [{start_time}] 遗留标记 - "
                f"日文原文「{japanese}」中包含译制辅助标记「{mark_str}」，要求删除。",
                results,
            )

        # 检查日文原文中的常规引号
        quote_found = _QUOTE_RE.findall(japanese)
        if quote_found:
            quote_str = "".join(set(quote_found))
            _emit(
                f"[格式] [{start_time}] 引号格式 - "
                f"日文原文「{japanese}」中包含常规引号「{quote_str}」，建议替换为「」。",
                results,
            )

        # 检查日文原文中的半角片假名
        half_kana_found = _HALF_KANA_RE.findall(japanese)
        if half_kana_found:
            half_kana_str = "".join(set(half_kana_found))
            _emit(
                f"[格式] [{start_time}] 半角片假名 - "
                f"日文原文「{japanese}」中包含半角片假名「{half_kana_str}」，建议替换为全角片假名。",
                results,
            )

    return results
