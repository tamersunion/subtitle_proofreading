#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import json
import re
from pathlib import Path
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI
from langchain_core.output_parsers import StrOutputParser
import asyncio
import pysubs2

# 过滤支持思考模型的推理标签（如 <think>、<thinking> 等）
_THINK_RE = re.compile(
    r"<(think|thinking|thought|reasoning|analysis)[^>]*>.*?</\1>",
    re.DOTALL | re.IGNORECASE,
)

def _strip_thinking(text: str) -> str:
    """移除模型思考过程标签及其内容"""
    if not text:
        return text
    return _THINK_RE.sub("", text).strip()


def _format_timestamp(ms: int) -> str:
    """将毫秒统一格式化为 HH:MM:SS.cc"""
    total_seconds = ms // 1000
    hours = total_seconds // 3600
    minutes = (total_seconds % 3600) // 60
    seconds = total_seconds % 60
    centiseconds = (ms % 1000) // 10
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}.{centiseconds:02d}"

_CONFIG_PATH = Path(__file__).with_name("config.json")
with _CONFIG_PATH.open("r", encoding="utf-8") as _cf:
    CONFIG = json.load(_cf)

client = ChatOpenAI(**CONFIG["llm_params"])

# 检查类别与对应规则文件映射
_CATEGORY_MAP = {
    "jp_source": "jp_source_rules.xml",
    "translation": "translation_rules.xml",
    "glossary": "glossary_rules.xml",
    "grammar": "grammar_rules.xml",
}

_LABEL_MAP = {
    "jp_source": "[原文]", # 原文检查
    "translation": "[翻译]", # 翻译检查
    "glossary": "[术语]", # 术语检查
    "grammar": "[语法]", # 语法排版检查等其他问题
}


def _load_prompt(category: str) -> str:
    """按检查类别加载对应的 SYSTEM_PROMPT"""
    prompt_dir = Path(__file__).with_name("prompts")
    data_dir = Path(__file__).with_name("data")

    parts = []

    # 1. Role
    parts.append((prompt_dir / "role.xml").read_text(encoding="utf-8"))

    # 2. Objective
    parts.append((prompt_dir / "objective.xml").read_text(encoding="utf-8"))

    # 3. 对应类别的 Guidelines
    rule_file = _CATEGORY_MAP[category]
    rule_content = (prompt_dir / rule_file).read_text(encoding="utf-8")
    parts.append(f"<Guidelines>\n{rule_content}\n</Guidelines>")

    # 4. Glossary（所有类别均加载，术语检查为强制规范，其他类别供参考）
    glossary_content = (data_dir / "glossary.xml").read_text(encoding="utf-8")
    if category == "glossary":
        parts.append(glossary_content)
    else:
        parts.append(f"以下译名表供参考，如遇专有名词可对照确认。\n{glossary_content}")

    # 5. OutputFormat
    parts.append((prompt_dir / "output_format.xml").read_text(encoding="utf-8"))

    return "\n\n".join(parts)


def read_ass_as_xml(file: Path, splitter: str = r"\N{\fnG-OTF Jo Shin Maru Go ProN M\fs45}", style: str = "Default"):
    subs = pysubs2.load(str(file))
    for line in subs:
        if line.is_comment or line.style != style:
            continue

        start_time = _format_timestamp(line.start)
        text = line.text
        if len(text.strip()) == 0:
            continue
        if splitter not in text:
            print(f"[预检] [{start_time}] 拆行失败 - 字幕行未找到中日文分隔符，已跳过：{text}")
            continue
        chinese, japanese = text.split(splitter, 1)
        yield f"<TranslationLine><StartTime>{start_time}</StartTime><ChineseText>{chinese.strip()}</ChineseText><JapaneseText>{japanese.strip()}</JapaneseText></TranslationLine>"


async def _check_chunk(chunk: list[str], category: str, strParser: StrOutputParser) -> str:
    """对单个 chunk 执行某一类别的检查（SystemMessage 携带 cache_control 缓存标记）"""
    prompt = _load_prompt(category)
    content_item = {"type": "text", "text": prompt}
    llm_extra = CONFIG.get("llm_extra", {})
    if isinstance(llm_extra, dict) and llm_extra:
        content_item.update(llm_extra)
    system_msg = SystemMessage(content=[content_item])
    human = HumanMessage(
        "<Task>请校对以下字幕<Task>\n<Subtitle>\n{}\n</Subtitle>".format("\n".join(chunk))
    )
    msgs = [system_msg, human]
    result = await client.ainvoke(msgs)
    text = strParser.invoke(result)
    return _strip_thinking(text)


async def _check_chunk_with_label(chunk: list[str], category: str, strParser: StrOutputParser) -> str:
    """执行检查，类型标签插入到时间戳之后，完成后实时打印"""
    result = await _check_chunk(chunk, category, strParser)
    if result and result.strip():
        prefix = _LABEL_MAP.get(category, f"[{category}]")
        lines = result.strip().splitlines()
        output_lines = []
        for line in lines:
            line = line.strip()
            if not line:
                continue
            match = re.match(r'^(\[\d{2}:\d{2}:\d{2}\.\d{2}\])\s+(.*)', line)
            if match:
                timestamp, rest = match.groups()
                output_lines.append(f"{prefix} {timestamp} {rest}")
            else:
                output_lines.append(f"{prefix} {line}")
        output = "\n".join(output_lines)
        print(output)
        return output
    return ""


async def _check_chunk_parallel(chunk: list[str], strParser: StrOutputParser) -> str:
    """先发起一条提高缓存命中率，完成后剩余3条并行并实时打印"""
    # 第一阶段：先完成 translation（通常核心检查，用于预热缓存）
    first_result = await _check_chunk_with_label(chunk, "translation", strParser)

    # 第二阶段：剩余3条并行，各自完成后实时打印
    remaining = [c for c in _CATEGORY_MAP.keys() if c != "translation"]
    tasks = [asyncio.create_task(_check_chunk_with_label(chunk, cat, strParser)) for cat in remaining]
    rest_results = await asyncio.gather(*tasks)

    # 合并所有结果
    all_results = [first_result] + list(rest_results)
    merged = "\n".join(r for r in all_results if r)
    return merged


async def check_ass(file: Path, chunk_size: int = 30, splitter: str = r"\N{\fnG-OTF Jo Shin Maru Go ProN M\fs45}", style: str = "Default") -> list[str]:
    """对 ASS 文件进行 AI 多类别并行检查，返回结果列表"""
    lines = list(read_ass_as_xml(file, splitter, style))
    total_response = []
    strParser = StrOutputParser()

    for i in range(0, len(lines), chunk_size):
        chunk = lines[i: i + chunk_size]
        response = await _check_chunk_parallel(chunk, strParser)
        total_response.append(response)

    return total_response
