#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import argparse
import json
import base64
import urllib.request
from urllib.parse import quote
from pathlib import Path
from datetime import datetime
from convert_dict_to_xml import convert_to_xml
from char_format_check import check_char_format
from ai_checker import check_ass

_CONFIG_PATH = Path(__file__).with_name("config.json")
with _CONFIG_PATH.open("r", encoding="utf-8") as _cf:
    CONFIG = json.load(_cf)

now = datetime.now()
timestamp = now.strftime(CONFIG.get("timestamp_format", "%Y%m%d-%H%M%S-%f"))


def download_glossary_from_webdav() -> Path:
    """从 WebDAV 下载译名表并转换为 glossary.xml"""
    webdav_cfg = CONFIG.get("webdav", {})
    base_url = webdav_cfg.get("base_url", "").rstrip("/")
    username = webdav_cfg.get("username", "")
    password = webdav_cfg.get("password", "")
    filepath = webdav_cfg.get("filepath", "path/to/glossary.xlsx")

    if not base_url or not username or not password:
        raise ValueError("WebDAV 配置不完整，请检查 config.json 中的 webdav 字段")

    download_url = f"{base_url}/{quote(filepath)}"
    local_path = Path(webdav_cfg.get("local_path", "data/glossary.xlsx"))
    local_path.parent.mkdir(parents=True, exist_ok=True)

    creds = base64.b64encode(f"{username}:{password}".encode()).decode()
    req = urllib.request.Request(
        download_url,
        headers={"Authorization": f"Basic {creds}"}
    )

    print(f"正在从 WebDAV 下载: {download_url}")
    with urllib.request.urlopen(req) as resp:
        local_path.write_bytes(resp.read())
    print(f"下载完成: {local_path}")

    glossary_path = Path(__file__).with_name("data") / "glossary.xml"
    convert_to_xml(str(local_path), str(glossary_path))
    print(f"译名表已更新: {glossary_path}")

    return glossary_path


class WideHelpFormatter(argparse.RawDescriptionHelpFormatter):
    def __init__(self, prog):
        super().__init__(prog, max_help_position=40, width=100)


async def main():
    parser = argparse.ArgumentParser(
        prog="subtitle_proofreading.py",
        description="中日字幕校对工具 - 通过 LLM 自动校对 .ass 字幕文件",
        epilog="""示例:
  %(prog)s -f episode01.ass
  %(prog)s -f episode01.ass -o result.txt
  %(prog)s -u
""",
        formatter_class=WideHelpFormatter,
        add_help=False,
    )
    parser._optionals.title = "选项"

    parser.add_argument("-h", "--help", action="help", default=argparse.SUPPRESS,
                        help="显示帮助信息并退出")
    parser.add_argument("-f", "--file", type=Path, metavar="路径", required=False,
                        help="输入的 .ass 字幕文件路径")
    parser.add_argument("-o", "--output", type=Path, metavar="路径", default=None,
                        help="输出结果文件路径（默认为 result-<timestamp>.txt）")
    parser.add_argument("-u", "--update-glossary", action="store_true",
                        help="仅更新译名表后退出")
    parser.add_argument("-s", "--skip-glossary-update", action="store_true",
                        help="跳过译名表更新，直接使用本地缓存")

    def _error(message):
        parser.print_help()
        print(f"\nerror: {message}")
        parser.exit(2)

    parser.error = _error
    args = parser.parse_args()

    if args.update_glossary:
        download_glossary_from_webdav()
        return

    if not args.file:
        parser.error("必须指定 --file 或使用 --update-glossary")

    # 每次运行都同步最新译名表（除非跳过）
    if not args.skip_glossary_update:
        download_glossary_from_webdav()

    assfile = args.file
    template = CONFIG.get("output_filename_template", "result-{timestamp}.txt")
    output = args.output or Path(template.format(timestamp=timestamp))

    # 1. 字符格式静态检查（结果已在函数内实时打印）
    splitter = CONFIG.get("subtitle_splitter", r"\N{\fnG-OTF Jo Shin Maru Go ProN M\fs45}")
    style = CONFIG.get("subtitle_style", "Default")
    static_results = check_char_format(assfile, splitter, style)

    # 2. AI 动态检查（结果已在函数内实时打印）
    ai_results = await check_ass(assfile, CONFIG.get("chunk_size", 30), splitter, style)

    # 合并输出到文件
    total_response = static_results + ai_results
    with output.open("w", encoding="utf-8") as ofs:
        ofs.write("\n".join(total_response))


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
