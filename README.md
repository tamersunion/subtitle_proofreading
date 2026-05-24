# 字幕校对工具

AI 辅助中日双语字幕校对工具，支持 ASS 格式字幕文件的静态格式检查与 AI 动态语义检查。

## 功能

### 字符格式静态检查
基于正则的规则引擎，无需 AI 即可快速检测常见格式问题：

- **空格规范**：中文译文禁用全角空格，日文原文禁用半角空格
- **标点符号**：禁用中文逗号、顿号、句号等；中文译文禁用波浪号、省略号
- **引号格式**：所有 `""` `''` 变体必须替换为 `「」`
- **遗留标记**：`* # /` 等译制辅助符号
- **半角片假名**：日文原文中不得出现
- **全角空格前后**：日文原文开头/结尾的全角空格会导致字幕移位无法居中

### AI 动态检查
通过 LLM（默认阿里云 qwen3.6-plus）进行语义层面的多维度检查：

| 类别 | 检查内容 |
|------|---------|
| `translation` | 翻译质量、语序、用词、日式中文、逻辑衔接 |
| `jp_source` | 日文原文完整性、断句合理性、语气保留 |
| `glossary` | 专有名词（角色名、技能名、地名）与术语表一致性 |
| `grammar` | 语法错误、代词使用、标点遗漏、语体不当 |

采用 **1+3 并行策略**：`translation` 先执行预热缓存，剩余三类并行执行，最大化缓存命中率。

### 术语表同步
支持从 WebDAV 自动下载译名表 xlsx，转换为 `data/glossary.xml` 供 AI 参考。所有检查轮次均加载术语表。

## 快速开始

### 依赖

```bash
pip install langchain-openai pysubs2 openpyxl tqdm pandas
```

### 配置

复制示例配置并填写实际参数：

```bash
cp config.example.json config.json
```

关键配置项说明：

```json
{
    "llm_params": {
        "model": "qwen3.6-plus",
        "api_key": "your-api-key",
        "base_url": "https://your-api-host.com/v1/"
    },
    "subtitle_splitter": "\\N{\\fnG-OTF Jo Shin Maru Go ProN M\\fs45}",
    "subtitle_style": "Default",
    "webdav": {
        "base_url": "https://cloud.example.com/remote.php/dav/files/user",
        "username": "user",
        "password": "pass",
        "filepath": "译名表.xlsx",
        "local_path": "data/译名表.xlsx"
    }
}
```

### 使用

```bash
# 基本用法
python subtitle_proofreading.py -f subtitle.ass

# 指定输出文件
python subtitle_proofreading.py -f subtitle.ass -o result.txt

# 仅更新术语表
python subtitle_proofreading.py -u

# 跳过术语表更新（使用本地缓存）
python subtitle_proofreading.py -f subtitle.ass -s
```

## 输出格式

所有结果统一为以下格式：

```
[分类] [HH:MM:SS.cc] 问题类型 - 描述
```

示例：

```
[语法/排版] [00:01:23.45] 标点违规 - 译文"你好。"中包含违规句号和双引号，建议删除句号并改为「你好」。
[术语] [00:03:05.00] 代词错误 - 原文指向数码兽，译文"他怎么了"误用"他"，建议改为"它"。
[翻译] [00:04:12.30] 逻辑/错译 - 原文「ああして、こうして」包含多个「して」，译文"这样，那样"未处理逻辑衔接，建议重组句式。
```

结果会同时打印到终端并写入文件。

## 文件结构

```
.
├── subtitle_proofreading.py   # 入口文件，负责参数解析与流程编排
├── ai_checker.py              # AI 检查核心：prompt 加载、多轮并行检查
├── char_format_check.py       # 静态格式检查引擎
├── convert_dict_to_xml.py     # 译名表 xlsx → xml 转换
├── prompts/                   # 各类别检查规则（XML 格式）
│   ├── role.xml
│   ├── objective.xml
│   ├── output_format.xml
│   ├── translation_rules.xml
│   ├── jp_source_rules.xml
│   ├── glossary_rules.xml
│   └── grammar_rules.xml
├── data/
│   └── glossary.xml           # 术语表（自动同步生成）
|   └── glossary.xlsx          # 术语表（从 WebDAV 下载）
├── config.json                # 运行配置（从 example 复制后填写）
└── config.example.json        # 配置示例
```

## License

MIT
