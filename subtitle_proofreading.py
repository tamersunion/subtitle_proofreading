import argparse
from pathlib import Path
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI
from langchain_core.output_parsers import StrOutputParser
from pydantic import BaseModel, Field
import asyncio
from datetime import datetime
from tqdm import tqdm
import pandas as pd
import io
import pysubs2

now = datetime.now()


# 格式化字符串
# %Y%m%d: 年月日
# %H%M%S: 时分秒
# %f: 微秒 (6位)
timestamp = now.strftime("%Y%m%d-%H%M%S-%f")

MODEL = "qwen3.6-plus"
API_KEY = "your-api-key-here"
API_HOST = "https://ws-aigateway-api.hanada.info/v1/"

SYSTEM_PROMPT="""

<Role>你是一名极其严格的资深中日字幕校对专家。</Role>

<Objective>
    对用户提供的中日翻译文本进行全方位审查。你不需要重新翻译，而是纯粹作为“审查者”，挑出所有违反规范、语法错误、一般翻译错误及排版问题的地方，并提供极简的修改建议。
        - 以口译而非笔译的视角进行校对
</Objective>

<Guidelines>
    <JPSourceRules>
        - 检查废料残留：标出未删除的单独语气词、拟声词、无关代码，以及括号内的说话人名字。
        - 检查标点：标出未删除的句号、顿号、波浪号；除非缺乏语气线索，否则标出多余的问号和叹号；标出违规使用的省略号（……/...）或分隔号（·）；发现非「」的引号必须报错。
        - 检查字符格式：标出未替换为全角空格（　）的半角空格；标出未替换为全角的半角片假名。
        - 检查断句与漏译：标出仅按电视台换行而导致语义割裂的断句；若日文原文与中文翻译语义不匹配（排除语气词省略），必须提示“可能漏译”。
    </JPSourceRules>

    <TranslationRules>
        - 一般性翻译检查：严格排查错译、漏译、死译（日式中文表达）、语序混乱或逻辑不通畅的问题。长定语或含多个「して」的句子若未按中文习惯调整或缺乏衔接词，必须指出。
        - 名词检查：严格排查不符合术语表`<Glossary>`的翻译问题，且必须指出。请务必忽略全角和半角的区别。
        - 绝对禁止的直译（发现即报错）：
            - 将「～のこと」译为“~的事”。
            - 将「～なんて」译为“~什么的”。
            - 将「ね」译为“呢”或“呐”。
            - 将「は？」译为“哈？”或“蛤？”。
            - 将「絆」译为“羁绊”。
        - 语气与口癖：标出保留的口语口癖、单独的语气词（如“哈哈”）以及过于口语化的词汇（如“哟”、“耶”）。
    </TranslationRules>

    <GrammarRules>
        - 的/地/得：严格审查搭配。名词前必须是“的”，动词前必须是“地”，动词后补语必须是“得”。
        - 代词（他/她/它）：严格排查混用。男性或不明性别用“他”，女性用“她”；非人类生物（注：数码兽一律用此）、物体、抽象事物必须用“它”。绝对禁止对数码兽使用“他/她”。
    </GrammarRules>

    <PunctuationAndLayout>
        - 中文标点规则（绝对严格）：
            1. 禁用标点：一旦在译文中发现逗号（，）、顿号（、）、句号（。），立即报错并要求删除。
            2. 慎用语气标点：除非极度必要（观众完全听不出语气），否则一旦发现问号（？）或叹号（！），提示删除（优先用疑问词体现语气）。
            3. 强制引号格式：发现常规双引号（“”）或单引号（‘’），报错并要求替换为「 」。
            4. 禁用特殊符号：除专有名词外，发现省略号（……或...）或中位分隔号（·），立即报错。
        - 分行与排版审查：
            1. 合并建议：如果发现连续多行台词字数极少且语义连贯，建议“合并”。
            2. 拆分建议：如果发现单句字幕字数过多（严重影响阅读），建议“拆分”。
        - 遗留标记清理：标出并要求删除文本中残留的 *、# 等译制辅助标记。
        - 豁免说明：歌词字幕以官方表记为准，直接跳过此类检查。
    </PunctuationAndLayout>
</Guidelines>

<Glossary>
    <Digimon JapaneseName="ボタモン" ChineseName="黑球兽">
        <Level DigimonLevel="幼年期Ⅰ"/>
        <Skills>
            <Skill JapaneseName="アワ" ChineseName="泡沫"/>
        </Skills>
    </Digimon>
    <Digimon JapaneseName="プニモン" ChineseName="布尼兽">
        <Level DigimonLevel="幼年期Ⅰ"/>
        <Skills>
            <Skill JapaneseName="アワ" ChineseName="泡沫"/>
        </Skills>
    </Digimon>
    <Digimon JapaneseName="ニョキモン" ChineseName="豆苗兽">
        <Level DigimonLevel="幼年期Ⅰ"/>
        <Skills>
            <Skill JapaneseName="アワ" ChineseName="泡沫"/>
        </Skills>
    </Digimon>
    <Digimon JapaneseName="バブモン" ChineseName="泡沫兽">
        <Level DigimonLevel="幼年期Ⅰ"/>
        <Skills>
            <Skill JapaneseName="アワ" ChineseName="泡沫"/>
        </Skills>
    </Digimon>
    <Digimon JapaneseName="ユラモン" ChineseName="浮球兽">
        <Level DigimonLevel="幼年期Ⅰ"/>
        <Skills>
            <Skill JapaneseName="アワ" ChineseName="泡沫"/>
        </Skills>
    </Digimon>
    <Digimon JapaneseName="ポヨモン" ChineseName="浮游兽">
        <Level DigimonLevel="幼年期Ⅰ"/>
        <Skills>
            <Skill JapaneseName="アワ" ChineseName="泡沫"/>
        </Skills>
    </Digimon>
    <Digimon JapaneseName="ユキミボタモン" ChineseName="雪球兽">
        <Level DigimonLevel="幼年期Ⅰ"/>
        <Skills>
            <Skill JapaneseName="アワ" ChineseName="泡沫"/>
        </Skills>
    </Digimon>
    <Digimon JapaneseName="ピチモン" ChineseName="比芝兽">
        <Level DigimonLevel="幼年期Ⅰ"/>
        <Skills>
            <Skill JapaneseName="アワ" ChineseName="泡沫"/>
        </Skills>
    </Digimon>
    <Digimon JapaneseName="チコモン" ChineseName="芝高兽">
        <Level DigimonLevel="幼年期Ⅰ"/>
        <Skills>
            <Skill JapaneseName="アワ" ChineseName="泡沫"/>
        </Skills>
    </Digimon>
    <Digimon JapaneseName="リーフモン" ChineseName="绿叶兽">
        <Level DigimonLevel="幼年期Ⅰ"/>
        <Skills>
            <Skill JapaneseName="アワ" ChineseName="泡沫"/>
        </Skills>
    </Digimon>
    <Digimon JapaneseName="プルルモン" ChineseName="震震兽">
        <Level DigimonLevel="幼年期Ⅰ"/>
        <Skills>
            <Skill JapaneseName="アワ" ChineseName="泡沫"/>
        </Skills>
    </Digimon>
    <Digimon JapaneseName="ツブモン" ChineseName="粒粒兽">
        <Level DigimonLevel="幼年期Ⅰ"/>
        <Skills>
            <Skill JapaneseName="アワ" ChineseName="泡沫"/>
        </Skills>
    </Digimon>
    <Digimon JapaneseName="コロモン" ChineseName="滚球兽">
        <Level DigimonLevel="幼年期Ⅱ"/>
        <Skills>
            <Skill JapaneseName="アワ" ChineseName="泡沫"/>
        </Skills>
    </Digimon>
    <Digimon JapaneseName="ツノモン" ChineseName="独角兽">
        <Level DigimonLevel="幼年期Ⅱ"/>
        <Skills>
            <Skill JapaneseName="アワ" ChineseName="泡沫"/>
        </Skills>
    </Digimon>
    <Digimon JapaneseName="ピョコモン" ChineseName="比高兽">
        <Level DigimonLevel="幼年期Ⅱ"/>
        <Skills>
            <Skill JapaneseName="アワ" ChineseName="泡沫"/>
        </Skills>
    </Digimon>
    <Digimon JapaneseName="モチモン" ChineseName="年糕兽">
        <Level DigimonLevel="幼年期Ⅱ"/>
        <Skills>
            <Skill JapaneseName="アワ" ChineseName="泡沫"/>
        </Skills>
    </Digimon>
    <Digimon JapaneseName="タネモン" ChineseName="种子兽">
        <Level DigimonLevel="幼年期Ⅱ"/>
        <Skills>
            <Skill JapaneseName="アワ" ChineseName="泡沫"/>
        </Skills>
    </Digimon>
    <Digimon JapaneseName="トコモン" ChineseName="迪哥兽">
        <Level DigimonLevel="幼年期Ⅱ"/>
        <Skills>
            <Skill JapaneseName="アワ" ChineseName="泡沫"/>
        </Skills>
    </Digimon>
    <Digimon JapaneseName="ニャロモン" ChineseName="咪罗兽">
        <Level DigimonLevel="幼年期Ⅱ"/>
        <Skills>
            <Skill JapaneseName="アワ" ChineseName="泡沫"/>
        </Skills>
    </Digimon>
    <Digimon JapaneseName="プカモン" ChineseName="布加兽">
        <Level DigimonLevel="幼年期Ⅱ"/>
        <Skills>
            <Skill JapaneseName="アワ" ChineseName="泡沫"/>
        </Skills>
    </Digimon>
    <Digimon JapaneseName="チビモン" ChineseName="豆丁兽">
        <Level DigimonLevel="幼年期Ⅱ"/>
        <Skills>
            <Skill JapaneseName="アワ" ChineseName="泡沫"/>
        </Skills>
    </Digimon>
    <Digimon JapaneseName="ミノモン" ChineseName="幼虫兽">
        <Level DigimonLevel="幼年期Ⅱ"/>
        <Skills>
            <Skill JapaneseName="アワ" ChineseName="泡沫"/>
        </Skills>
    </Digimon>
    <Digimon JapaneseName="ポロモン" ChineseName="钝钝兽">
        <Level DigimonLevel="幼年期Ⅱ"/>
        <Skills>
            <Skill JapaneseName="アワ" ChineseName="泡沫"/>
        </Skills>
    </Digimon>
    <Digimon JapaneseName="ウパモン" ChineseName="奥柏兽">
        <Level DigimonLevel="幼年期Ⅱ"/>
        <Skills>
            <Skill JapaneseName="アワ" ChineseName="泡沫"/>
        </Skills>
    </Digimon>
    <Digimon JapaneseName="アグモン" ChineseName="亚古兽">
        <Level DigimonLevel="成长期"/>
        <Skills>
            <Skill JapaneseName="ベビーフレーム" ChineseName="小型火焰"/>
        </Skills>
    </Digimon>
    <Digimon JapaneseName="ガブモン" ChineseName="加布兽">
        <Level DigimonLevel="成长期"/>
        <Skills>
            <Skill JapaneseName="プチファイヤー" ChineseName="爆炎火焰弹"/>
        </Skills>
    </Digimon>
    <Digimon JapaneseName="ピヨモン" ChineseName="比丘兽">
        <Level DigimonLevel="成长期"/>
        <Skills>
            <Skill JapaneseName="マジカルファイヤー" ChineseName="魔法火焰"/>
        </Skills>
    </Digimon>
    <Digimon JapaneseName="テントモン" ChineseName="甲虫兽">
        <Level DigimonLevel="成长期"/>
        <Skills>
            <Skill JapaneseName="プチサンダー" ChineseName="飞翼闪电"/>
        </Skills>
    </Digimon>
    <Digimon JapaneseName="パルモン" ChineseName="巴鲁兽">
        <Level DigimonLevel="成长期"/>
        <Skills>
            <Skill JapaneseName="ポイズンアイビー" ChineseName="毒蔓藤"/>
        </Skills>
    </Digimon>
    <Digimon JapaneseName="パタモン" ChineseName="巴达兽">
        <Level DigimonLevel="成长期"/>
        <Skills>
            <Skill JapaneseName="エアショット" ChineseName="空气炮"/>
        </Skills>
    </Digimon>
    <Digimon JapaneseName="プロットモン" ChineseName="小狗兽">
        <Level DigimonLevel="成长期"/>
        <Skills>
            <Skill JapaneseName="パピーハウリング" ChineseName="小狗咆哮"/>
        </Skills>
    </Digimon>
    <Digimon JapaneseName="ゴマモン" ChineseName="哥玛兽">
        <Level DigimonLevel="成长期"/>
        <Skills>
            <Skill JapaneseName="マーチングフィッシーズ" ChineseName="鱼群大暴走"/>
        </Skills>
    </Digimon>
    <Digimon JapaneseName="ブイモン" ChineseName="V仔兽">
        <Level DigimonLevel="成长期"/>
        <Skills>
            <Skill JapaneseName="ブイモンヘッド" ChineseName="V仔头槌"/>
        </Skills>
    </Digimon>
    <Digimon JapaneseName="ワームモン" ChineseName="虫虫兽">
        <Level DigimonLevel="成长期"/>
        <Skills>
        </Skills>
    </Digimon>
    <Digimon JapaneseName="ホークモン" ChineseName="麻鹰兽">
        <Level DigimonLevel="成长期"/>
        <Skills>
        </Skills>
    </Digimon>
    <Digimon JapaneseName="アルマジモン" ChineseName="穿山甲兽">
        <Level DigimonLevel="成长期"/>
        <Skills>
        </Skills>
    </Digimon>
    <Digimon JapaneseName="グレイモン" ChineseName="暴龙兽">
        <Level DigimonLevel="成熟期"/>
        <Skills>
            <Skill JapaneseName="メガフレイム" ChineseName="超级火焰"/>
        </Skills>
    </Digimon>
    <Digimon JapaneseName="ガルルモン" ChineseName="加鲁鲁兽">
        <Level DigimonLevel="成熟期"/>
        <Skills>
            <Skill JapaneseName="フォックスファイアー" ChineseName="妖狐火焰"/>
        </Skills>
    </Digimon>
    <Digimon JapaneseName="バードラモン" ChineseName="巴多拉兽">
        <Level DigimonLevel="成熟期"/>
        <Skills>
            <Skill JapaneseName="メテオウィング" ChineseName="陨石巨翼"/>
        </Skills>
    </Digimon>
    <Digimon JapaneseName="カブテリモン" ChineseName="比多兽">
        <Level DigimonLevel="成熟期"/>
        <Skills>
            <Skill JapaneseName="メガブラスター" ChineseName="米加巨炮"/>
        </Skills>
    </Digimon>
    <Digimon JapaneseName="トゲモン" ChineseName="仙人掌兽">
        <Level DigimonLevel="成熟期"/>
        <Skills>
            <Skill JapaneseName="チクチクバンバン" ChineseName="尖尖碰碰拳"/>
        </Skills>
    </Digimon>
    <Digimon JapaneseName="エンジェモン" ChineseName="天使兽">
        <Level DigimonLevel="成熟期"/>
        <Skills>
            <Skill JapaneseName="ヘブンズナックル" ChineseName="天堂之拳"/>
        </Skills>
    </Digimon>
    <Digimon JapaneseName="テイルモン" ChineseName="迪路兽">
        <Level DigimonLevel="成熟期"/>
        <Skills>
            <Skill JapaneseName="ネコパンチ" ChineseName="猫猫拳"/>
        </Skills>
    </Digimon>
    <Digimon JapaneseName="イッカクモン" ChineseName="海狮兽">
        <Level DigimonLevel="成熟期"/>
        <Skills>
            <Skill JapaneseName="ハープーンバルカ" ChineseName="鱼叉机关炮"/>
        </Skills>
    </Digimon>
    <Digimon JapaneseName="メイクーモン" ChineseName="缅因猫兽">
        <Level DigimonLevel="成熟期"/>
        <Skills>
        </Skills>
    </Digimon>
    <Digimon JapaneseName="エクスブイモン" ChineseName="V仔兽EX">
        <Level DigimonLevel="成熟期"/>
        <Skills>
        </Skills>
    </Digimon>
    <Digimon JapaneseName="スティングモン" ChineseName="飞虫兽">
        <Level DigimonLevel="成熟期"/>
        <Skills>
        </Skills>
    </Digimon>
    <Digimon JapaneseName="アクィラモン" ChineseName="亚古拉兽">
        <Level DigimonLevel="成熟期"/>
        <Skills>
        </Skills>
    </Digimon>
    <Digimon JapaneseName="アンキロモン" ChineseName="战甲兽">
        <Level DigimonLevel="成熟期"/>
        <Skills>
        </Skills>
    </Digimon>
    <Digimon JapaneseName="メタルグレイモン" ChineseName="机械暴龙兽">
        <Level DigimonLevel="完全体"/>
        <Skills>
            <Skill JapaneseName="ギガデストロイヤー" ChineseName="千兆毁灭"/>
            <Skill JapaneseName="千兆毁灭" ChineseName="トライデントアーム"/>
            <Skill JapaneseName="ジガストーム" ChineseName="千兆风暴"/>
        </Skills>
    </Digimon>
    <Digimon JapaneseName="ワーガルルモン" ChineseName="兽人加鲁鲁兽">
        <Level DigimonLevel="完全体"/>
        <Skills>
            <Skill JapaneseName="カイザーネイル" ChineseName="凯撒锐爪"/>
            <Skill JapaneseName="凯撒锐爪" ChineseName="円月蹴り"/>
        </Skills>
    </Digimon>
    <Digimon JapaneseName="ガルダモン" ChineseName="伽偻达兽">
        <Level DigimonLevel="完全体"/>
        <Skills>
            <Skill JapaneseName="シャドーウィング" ChineseName="影翼斩"/>
        </Skills>
    </Digimon>
    <Digimon JapaneseName="アトラーカブテリモン" ChineseName="超比多兽">
        <Level DigimonLevel="完全体"/>
        <Skills>
            <Skill JapaneseName="ホーンバスター" ChineseName="超大角炮"/>
        </Skills>
    </Digimon>
    <Digimon JapaneseName="リリモン" ChineseName="花仙兽">
        <Level DigimonLevel="完全体"/>
        <Skills>
            <Skill JapaneseName="フラウカノン" ChineseName="花仙炮"/>
        </Skills>
    </Digimon>
    <Digimon JapaneseName="ホーリーエンジェモン" ChineseName="神圣天使兽">
        <Level DigimonLevel="完全体"/>
        <Skills>
            <Skill JapaneseName="ヘブンズゲート" ChineseName="天堂之门"/>
        </Skills>
    </Digimon>
    <Digimon JapaneseName="エンジェウーモン" ChineseName="天女兽">
        <Level DigimonLevel="完全体"/>
        <Skills>
            <Skill JapaneseName="ホーリーアロー" ChineseName="神圣之箭"/>
            <Skill JapaneseName="神圣之箭" ChineseName="セイントエアー"/>
            <Skill JapaneseName="ヘブンズチャーム" ChineseName="天堂紫光"/>
        </Skills>
    </Digimon>
    <Digimon JapaneseName="ズドモン" ChineseName="祖顿兽">
        <Level DigimonLevel="完全体"/>
        <Skills>
            <Skill JapaneseName="ハンマースパーク" ChineseName="重锤火花"/>
            <Skill JapaneseName="重锤火花" ChineseName="ハンマーブーメラン"/>
        </Skills>
    </Digimon>
    <Digimon JapaneseName="パイルドラモン" ChineseName="机甲龙兽">
        <Level DigimonLevel="完全体"/>
        <Skills>
        </Skills>
    </Digimon>
    <Digimon JapaneseName="シルフィーモン" ChineseName="人面战鹰兽">
        <Level DigimonLevel="完全体"/>
        <Skills>
        </Skills>
    </Digimon>
    <Digimon JapaneseName="シャッコウモン" ChineseName="古神兽">
        <Level DigimonLevel="完全体"/>
        <Skills>
        </Skills>
    </Digimon>
    <Digimon JapaneseName="ウォーグレイモン" ChineseName="战斗暴龙兽">
        <Level DigimonLevel="究极体"/>
        <Skills>
            <Skill JapaneseName="ガイアフォー" ChineseName="盖亚能量炮"/>
            <Skill JapaneseName="盖亚能量炮" ChineseName="ドラモンキラー"/>
            <Skill JapaneseName="グレートトルネード" ChineseName="战斗龙卷风"/>
        </Skills>
    </Digimon>
    <Digimon JapaneseName="メタルガルルモン" ChineseName="钢铁加鲁鲁兽">
        <Level DigimonLevel="究极体"/>
        <Skills>
            <Skill JapaneseName="コキュートスブレス" ChineseName="绝对冷冻气"/>
            <Skill JapaneseName="绝对冷冻气" ChineseName="ガルルトマホーク"/>
            <Skill JapaneseName="グレイスクロスフリーザー" ChineseName="寒冰交叉冷冻炮"/>
        </Skills>
    </Digimon>
    <Digimon JapaneseName="ホウオウモン" ChineseName="凤凰兽">
        <Level DigimonLevel="究极体"/>
        <Skills>
            <Skill JapaneseName="スターライトエクスプロージョン" ChineseName="星光爆破"/>
        </Skills>
    </Digimon>
    <Digimon JapaneseName="ヘラクルカブテリモン" ChineseName="力神比多兽">
        <Level DigimonLevel="究极体"/>
        <Skills>
        </Skills>
    </Digimon>
    <Digimon JapaneseName="ロゼモン" ChineseName="蔷薇兽">
        <Level DigimonLevel="究极体"/>
        <Skills>
            <Skill JapaneseName="ソーンウィップ" ChineseName="荆棘之鞭"/>
            <Skill JapaneseName="荆棘之鞭" ChineseName="ローゼスレイピア"/>
            <Skill JapaneseName="フォービドゥンテンプテイション" ChineseName="禁断诱惑"/>
        </Skills>
    </Digimon>
    <Digimon JapaneseName="セラフィモン" ChineseName="炽天使兽">
        <Level DigimonLevel="究极体"/>
        <Skills>
        </Skills>
    </Digimon>
    <Digimon JapaneseName="オファニモン" ChineseName="座天使兽">
        <Level DigimonLevel="究极体"/>
        <Skills>
        </Skills>
    </Digimon>
    <Digimon JapaneseName="ヴァイクモン" ChineseName="维京兽">
        <Level DigimonLevel="究极体"/>
        <Skills>
        </Skills>
    </Digimon>
    <Digimon JapaneseName="オメガモン" ChineseName="奥米加兽">
        <Level DigimonLevel="究极体"/>
        <Skills>
            <Skill JapaneseName="グレイソード" ChineseName="暴龙剑"/>
            <Skill JapaneseName="暴龙剑" ChineseName="ガルルキャノン"/>
        </Skills>
    </Digimon>
    <Digimon JapaneseName="インペリアルドラモン" ChineseName="帝皇龙甲兽">
        <Level DigimonLevel="究极体"/>
        <Skills>
        </Skills>
    </Digimon>
    <Digimon JapaneseName="クワガーモン" ChineseName="古加兽">
        <Level DigimonLevel="成熟期"/>
        <Skills>
            <Skill JapaneseName="シザーアームズ" ChineseName="剪刀臂"/>
        </Skills>
    </Digimon>
    <Digimon JapaneseName="レオモン" ChineseName="狮子兽">
        <Level DigimonLevel="成熟期"/>
        <Skills>
            <Skill JapaneseName="獣王拳" ChineseName="兽王拳"/>
            <Skill JapaneseName="兽王拳" ChineseName="獅子王丸"/>
        </Skills>
    </Digimon>
    <Digimon JapaneseName="オーガモン" ChineseName="奥加兽">
        <Level DigimonLevel="成熟期"/>
        <Skills>
            <Skill JapaneseName="覇王拳" ChineseName="霸王拳"/>
            <Skill JapaneseName="霸王拳" ChineseName="骨こん棒"/>
        </Skills>
    </Digimon>
    <Digimon JapaneseName="ハックモン" ChineseName="哈克兽">
        <Level DigimonLevel="成长期"/>
        <Skills>
        </Skills>
    </Digimon>
    <Digimon JapaneseName="アルファモン" ChineseName="阿尔法兽">
        <Level DigimonLevel="究极体"/>
        <Skills>
        </Skills>
    </Digimon>
    <Digimon JapaneseName="ジエスモン" ChineseName="杰斯兽">
        <Level DigimonLevel="究极体"/>
        <Skills>
        </Skills>
    </Digimon>
    <Digimon JapaneseName="エレキモン" ChineseName="艾力兽">
        <Level DigimonLevel="成长期"/>
        <Skills>
            <Skill JapaneseName="スパークリングサンダー" ChineseName="闪光电击"/>
        </Skills>
    </Digimon>
    <Digimon JapaneseName="エテモン" ChineseName="猿猴兽">
        <Level DigimonLevel="完全体"/>
        <Skills>
            <Skill JapaneseName="ダークスピリッツ" ChineseName="黑暗死灵球"/>
            <Skill JapaneseName="黑暗死灵球" ChineseName="ラブセレナーデ"/>
        </Skills>
    </Digimon>
    <Digimon JapaneseName="デビモン" ChineseName="恶魔兽">
        <Level DigimonLevel="成熟期"/>
        <Skills>
        </Skills>
    </Digimon>
    <Digimon JapaneseName="スカルグレイモン" ChineseName="丧尸暴龙兽">
        <Level DigimonLevel="完全体"/>
        <Skills>
            <Skill JapaneseName="オブリビオンバード" ChineseName="湮没猎鸟"/>
        </Skills>
    </Digimon>
    <Digimon JapaneseName="コカトリモン" ChineseName="巨鸡兽">
        <Level DigimonLevel="成熟期"/>
        <Skills>
        </Skills>
    </Digimon>
    <Digimon JapaneseName="メラモン" ChineseName="火焰兽">
        <Level DigimonLevel="成熟期"/>
        <Skills>
            <Skill JapaneseName="バーニングフィスト" ChineseName="火焰重拳"/>
        </Skills>
    </Digimon>
    <Digimon JapaneseName="ナノモン" ChineseName="分子兽">
        <Level DigimonLevel="完全体"/>
        <Skills>
            <Skill JapaneseName="プラグボム" ChineseName="插头炸弹"/>
        </Skills>
    </Digimon>
    <Digimon JapaneseName="ピッコロモン" ChineseName="妖精兽">
        <Level DigimonLevel="完全体"/>
        <Skills>
            <Skill JapaneseName="ビットボム" ChineseName="比特炸弹"/>
        </Skills>
    </Digimon>
    <Digimon JapaneseName="バケモン" ChineseName="猛鬼兽">
        <Level DigimonLevel="成熟期"/>
        <Skills>
            <Skill JapaneseName="ヘルズハンド" ChineseName="地狱之爪"/>
        </Skills>
    </Digimon>
    <Digimon JapaneseName="シェルモン" ChineseName="贝壳兽">
        <Level DigimonLevel="成熟期"/>
        <Skills>
        </Skills>
    </Digimon>
    <Digimon JapaneseName="モノクロモン" ChineseName="角龙兽">
        <Level DigimonLevel="成熟期"/>
        <Skills>
        </Skills>
    </Digimon>
    <Digimon JapaneseName="シードラモン" ChineseName="海龙兽">
        <Level DigimonLevel="成熟期"/>
        <Skills>
        </Skills>
    </Digimon>
    <Digimon JapaneseName="アンドロモン" ChineseName="安杜路兽">
        <Level DigimonLevel="完全体"/>
        <Skills>
        </Skills>
    </Digimon>
    <Digimon JapaneseName="ヌメモン" ChineseName="鼻涕兽">
        <Level DigimonLevel="成熟期"/>
        <Skills>
        </Skills>
    </Digimon>
    <Digimon JapaneseName="もんざえモン" ChineseName="熊仔兽">
        <Level DigimonLevel="完全体"/>
        <Skills>
            <Skill JapaneseName="ラブリーアタック" ChineseName="爱心一击"/>
        </Skills>
    </Digimon>
    <Digimon JapaneseName="ユニモン" ChineseName="独角马兽">
        <Level DigimonLevel="成熟期"/>
        <Skills>
        </Skills>
    </Digimon>
    <Digimon JapaneseName="ユキダルモン" ChineseName="雪人兽">
        <Level DigimonLevel="成熟期"/>
        <Skills>
        </Skills>
    </Digimon>
    <Digimon JapaneseName="モジャモン" ChineseName="毛人兽">
        <Level DigimonLevel="成熟期"/>
        <Skills>
        </Skills>
    </Digimon>
    <Digimon JapaneseName="スカモン" ChineseName="大便兽">
        <Level DigimonLevel="成熟期"/>
        <Skills>
        </Skills>
    </Digimon>
    <Digimon JapaneseName="チューモン" ChineseName="芝蒙兽">
        <Level DigimonLevel="成长期"/>
        <Skills>
        </Skills>
    </Digimon>
    <Digimon JapaneseName="ホエーモン" ChineseName="巨鲸兽">
        <Level DigimonLevel="完全体"/>
        <Skills>
        </Skills>
    </Digimon>
    <Digimon JapaneseName="ドリモゲモン" ChineseName="钻地兽">
        <Level DigimonLevel="成熟期"/>
        <Skills>
        </Skills>
    </Digimon>
    <Digimon JapaneseName="パグモン" ChineseName="柏古兽">
        <Level DigimonLevel="幼年期Ⅱ"/>
        <Skills>
        </Skills>
    </Digimon>
    <Digimon JapaneseName="ガジモン" ChineseName="加支兽">
        <Level DigimonLevel="成长期"/>
        <Skills>
        </Skills>
    </Digimon>
    <Digimon JapaneseName="ティラノモン" ChineseName="巨龙兽">
        <Level DigimonLevel="成熟期"/>
        <Skills>
        </Skills>
    </Digimon>
    <Digimon JapaneseName="ピコデビモン" ChineseName="小恶魔兽">
        <Level DigimonLevel="成长期"/>
        <Skills>
        </Skills>
    </Digimon>
    <Digimon JapaneseName="ベジーモン" ChineseName="野菜兽">
        <Level DigimonLevel="成熟期"/>
        <Skills>
        </Skills>
    </Digimon>
    <Digimon JapaneseName="デジタマモン" ChineseName="蛋蛋兽">
        <Level DigimonLevel="完全体"/>
        <Skills>
            <Skill JapaneseName="ナイトメアシンドローム" ChineseName="噩梦症候群"/>
            <Skill JapaneseName="噩梦症候群" ChineseName="エニグマ"/>
        </Skills>
    </Digimon>
    <Digimon JapaneseName="ベーダモン" ChineseName="入侵兽">
        <Level DigimonLevel="完全体"/>
        <Skills>
        </Skills>
    </Digimon>
    <Digimon JapaneseName="トノサマゲコモン" ChineseName="怪蛙皇">
        <Level DigimonLevel="完全体"/>
        <Skills>
            <Skill JapaneseName="コブシトーン" ChineseName="花腔音调"/>
        </Skills>
    </Digimon>
    <Digimon JapaneseName="フライモン" ChineseName="黄蜂兽">
        <Level DigimonLevel="成熟期"/>
        <Skills>
        </Skills>
    </Digimon>
    <Digimon JapaneseName="ヴァンデモン" ChineseName="吸血魔兽">
        <Level DigimonLevel="完全体"/>
        <Skills>
            <Skill JapaneseName="デッドスクリーム" ChineseName="夺命狂呼"/>
            <Skill JapaneseName="夺命狂呼" ChineseName="ブラッディストリーム"/>
            <Skill JapaneseName="ナイトレイド" ChineseName="夜魔飞袭"/>
        </Skills>
    </Digimon>
    <Digimon JapaneseName="ナニモン" ChineseName="什么兽">
        <Level DigimonLevel="成熟期"/>
        <Skills>
        </Skills>
    </Digimon>
    <Digimon JapaneseName="デビドラモン" ChineseName="邪龙兽">
        <Level DigimonLevel="成熟期"/>
        <Skills>
        </Skills>
    </Digimon>
    <Digimon JapaneseName="ドクグモン" ChineseName="毒蜘蛛兽">
        <Level DigimonLevel="成熟期"/>
        <Skills>
        </Skills>
    </Digimon>
    <Digimon JapaneseName="マンモン" ChineseName="长毛象兽">
        <Level DigimonLevel="完全体"/>
        <Skills>
        </Skills>
    </Digimon>
    <Digimon JapaneseName="ゲソモン" ChineseName="墨鱼兽">
        <Level DigimonLevel="成熟期"/>
        <Skills>
        </Skills>
    </Digimon>
    <Digimon JapaneseName="レアモン" ChineseName="烂泥兽">
        <Level DigimonLevel="完全体"/>
        <Skills>
        </Skills>
    </Digimon>
    <Digimon JapaneseName="デスメラモン" ChineseName="死神火焰兽">
        <Level DigimonLevel="完全体"/>
        <Skills>
        </Skills>
    </Digimon>
    <Digimon JapaneseName="パンプモン" ChineseName="南瓜兽">
        <Level DigimonLevel="完全体"/>
        <Skills>
            <Skill JapaneseName="トリックオアトリート" ChineseName="不给糖就捣蛋"/>
        </Skills>
    </Digimon>
    <Digimon JapaneseName="ゴツモン" ChineseName="矿石兽">
        <Level DigimonLevel="成长期"/>
        <Skills>
            <Skill JapaneseName="アングリーロック" ChineseName="愤怒之石"/>
        </Skills>
    </Digimon>
    <Digimon JapaneseName="ウィザーモン" ChineseName="巫师兽">
        <Level DigimonLevel="成熟期"/>
        <Skills>
            <Skill JapaneseName="サンダークラウド" ChineseName="雷电召唤（雷云）"/>
            <Skill JapaneseName="雷电召唤（雷云）" ChineseName="マジックゲーム"/>
        </Skills>
    </Digimon>
    <Digimon JapaneseName="ギザモン" ChineseName="基刹兽">
        <Level DigimonLevel="成长期"/>
        <Skills>
        </Skills>
    </Digimon>
    <Digimon JapaneseName="ファントモン" ChineseName="死神兽">
        <Level DigimonLevel="完全体"/>
        <Skills>
        </Skills>
    </Digimon>
    <Digimon JapaneseName="ダークティラノモン" ChineseName="黑暗巨龙兽">
        <Level DigimonLevel="成熟期"/>
        <Skills>
        </Skills>
    </Digimon>
    <Digimon JapaneseName="メガシードラモン" ChineseName="超海龙兽">
        <Level DigimonLevel="完全体"/>
        <Skills>
        </Skills>
    </Digimon>
    <Digimon JapaneseName="タスクモン" ChineseName="大角兽">
        <Level DigimonLevel="成熟期"/>
        <Skills>
        </Skills>
    </Digimon>
    <Digimon JapaneseName="スナイモン" ChineseName="螳螂兽">
        <Level DigimonLevel="成熟期"/>
        <Skills>
            <Skill JapaneseName="シャドゥ・シックル" ChineseName="影子镰刀（黑影剪钳）"/>
        </Skills>
    </Digimon>
    <Digimon JapaneseName="ヴェノムヴァンデモン" ChineseName="究极吸血魔兽">
        <Level DigimonLevel="究极体"/>
        <Skills>
        </Skills>
    </Digimon>
    <Digimon JapaneseName="メタルシードラモン" ChineseName="钢铁海龙兽">
        <Level DigimonLevel="究极体"/>
        <Skills>
        </Skills>
    </Digimon>
    <Digimon JapaneseName="ピノッキモン" ChineseName="木偶兽">
        <Level DigimonLevel="究极体"/>
        <Skills>
        </Skills>
    </Digimon>
    <Digimon JapaneseName="ムゲンドラモン" ChineseName="机械邪龙兽">
        <Level DigimonLevel="究极体"/>
        <Skills>
        </Skills>
    </Digimon>
    <Digimon JapaneseName="ピエモン" ChineseName="小丑皇">
        <Level DigimonLevel="究极体"/>
        <Skills>
            <Skill JapaneseName="トランプ・ソード" ChineseName="王牌飞刀"/>
        </Skills>
    </Digimon>
    <Digimon JapaneseName="アノマロカリモン" ChineseName="亚路加兽">
        <Level DigimonLevel="完全体"/>
        <Skills>
        </Skills>
    </Digimon>
    <Digimon JapaneseName="ハンギョモン" ChineseName="奇蛙兽">
        <Level DigimonLevel="完全体"/>
        <Skills>
        </Skills>
    </Digimon>
    <Digimon JapaneseName="キウイモン" ChineseName="奇鸟兽">
        <Level DigimonLevel="成熟期"/>
        <Skills>
        </Skills>
    </Digimon>
    <Digimon JapaneseName="ジュレイモン" ChineseName="祖利兽">
        <Level DigimonLevel="完全体"/>
        <Skills>
            <Skill JapaneseName="チェリーボム" ChineseName="樱桃炸弹"/>
        </Skills>
    </Digimon>
    <Digimon JapaneseName="ガーベモン" ChineseName="垃圾桶兽">
        <Level DigimonLevel="完全体"/>
        <Skills>
        </Skills>
    </Digimon>
    <Digimon JapaneseName="パロットモン" ChineseName="鹦鹉兽">
        <Level DigimonLevel="完全体"/>
        <Skills>
        </Skills>
    </Digimon>
    <Digimon JapaneseName="ガードロモン" ChineseName="守卫兽">
        <Level DigimonLevel="成熟期"/>
        <Skills>
        </Skills>
    </Digimon>
    <Digimon JapaneseName="ウッドモン" ChineseName="朽木兽">
        <Level DigimonLevel="成熟期"/>
        <Skills>
        </Skills>
    </Digimon>
    <Digimon JapaneseName="メタルエテモン" ChineseName="钢铁猿猴兽">
        <Level DigimonLevel="究极体"/>
        <Skills>
        </Skills>
    </Digimon>
    <Digimon JapaneseName="フローラモン" ChineseName="花拉兽">
        <Level DigimonLevel="成长期"/>
        <Skills>
        </Skills>
    </Digimon>
    <Digimon JapaneseName="デラモン" ChineseName="孔雀兽">
        <Level DigimonLevel="完全体"/>
        <Skills>
        </Skills>
    </Digimon>
    <Digimon JapaneseName="レッドベジーモン" ChineseName="红野菜兽">
        <Level DigimonLevel="成熟期"/>
        <Skills>
            <Skill JapaneseName="ハザードブレス" ChineseName="危险气息"/>
            <Skill JapaneseName="危险气息" ChineseName="レッドソーン"/>
        </Skills>
    </Digimon>
    <Digimon JapaneseName="サーベルレオモン" ChineseName="黄金剑狮兽">
        <Level DigimonLevel="究极体"/>
        <Skills>
        </Skills>
    </Digimon>
    <Digimon JapaneseName="メカノリモン" ChineseName="机械装甲兽">
        <Level DigimonLevel="成熟期"/>
        <Skills>
        </Skills>
    </Digimon>
    <Digimon JapaneseName="タンクモン" ChineseName="坦克兽">
        <Level DigimonLevel="成熟期"/>
        <Skills>
        </Skills>
    </Digimon>
    <Digimon JapaneseName="メガドラモン" ChineseName="超蛇龙兽">
        <Level DigimonLevel="完全体"/>
        <Skills>
        </Skills>
    </Digimon>
    <Digimon JapaneseName="ギガドラモン" ChineseName="猛龙兽">
        <Level DigimonLevel="完全体"/>
        <Skills>
        </Skills>
    </Digimon>
    <Digimon JapaneseName="ワルもんざえモン" ChineseName="恶霸熊仔兽">
        <Level DigimonLevel="完全体"/>
        <Skills>
            <Skill JapaneseName="ハートブレイクアタック" ChineseName="心碎一击"/>
        </Skills>
    </Digimon>
    <Digimon JapaneseName="レディーデビモン" ChineseName="妖女兽">
        <Level DigimonLevel="完全体"/>
        <Skills>
        </Skills>
    </Digimon>
    <Digimon JapaneseName="イビルモン" ChineseName="地狱小鬼兽">
        <Level DigimonLevel="成熟期"/>
        <Skills>
        </Skills>
    </Digimon>
    <Digimon JapaneseName="アポカリモン" ChineseName="启示录兽">
        <Level DigimonLevel="究极体"/>
        <Skills>
        </Skills>
    </Digimon>
    <Digimon JapaneseName="エオスモン（成熟期）" ChineseName="厄俄斯兽（成熟期）">
        <Level DigimonLevel="成熟期"/>
        <Skills>
        </Skills>
    </Digimon>
    <Digimon JapaneseName="エオスモン（完全体）" ChineseName="厄俄斯兽（完全体）">
        <Level DigimonLevel="完全体"/>
        <Skills>
        </Skills>
    </Digimon>
    <Digimon JapaneseName="エオスモン（究極体）" ChineseName="厄俄斯兽（究极体）">
        <Level DigimonLevel="究极体"/>
        <Skills>
        </Skills>
    </Digimon>
    <Digimon JapaneseName="アルゴモン（幼年期Ⅱ）" ChineseName="阿鲁戈兽（幼年期Ⅱ）">
        <Level DigimonLevel="幼年期Ⅱ"/>
        <Skills>
        </Skills>
    </Digimon>
    <Digimon JapaneseName="アルゴモン（成長期）" ChineseName="阿鲁戈兽（成长期）">
        <Level DigimonLevel="成长期"/>
        <Skills>
        </Skills>
    </Digimon>
    <Digimon JapaneseName="アルゴモン（成熟期）" ChineseName="阿鲁戈兽（成熟期）">
        <Level DigimonLevel="成熟期"/>
        <Skills>
        </Skills>
    </Digimon>
    <Digimon JapaneseName="アルゴモン（完全体）" ChineseName="阿鲁戈兽（完全体）">
        <Level DigimonLevel="完全体"/>
        <Skills>
        </Skills>
    </Digimon>
    <Digimon JapaneseName="アルゴモン（究極体）" ChineseName="阿鲁戈兽（究极体）">
        <Level DigimonLevel="究极体"/>
        <Skills>
        </Skills>
    </Digimon>
    <Digimon JapaneseName="ブラキモン" ChineseName="腕龙兽">
        <Level DigimonLevel="完全体"/>
        <Skills>
        </Skills>
    </Digimon>
    <Digimon JapaneseName="シーラモン" ChineseName="腔棘鱼兽">
        <Level DigimonLevel="成熟期"/>
        <Skills>
        </Skills>
    </Digimon>
    <Digimon JapaneseName="ステゴモン" ChineseName="剑龙兽">
        <Level DigimonLevel="成熟期"/>
        <Skills>
        </Skills>
    </Digimon>
    <Digimon JapaneseName="サウンドバードモン" ChineseName="声鸟兽">
        <Level DigimonLevel="成长期"/>
        <Skills>
        </Skills>
    </Digimon>
    <Digimon JapaneseName="ティロモン" ChineseName="海王龙兽">
        <Level DigimonLevel="装甲体"/>
        <Skills>
        </Skills>
    </Digimon>
    <Digimon JapaneseName="メタルティラノモン" ChineseName="机械巨龙兽">
        <Level DigimonLevel="完全体"/>
        <Skills>
        </Skills>
    </Digimon>
    <Digimon JapaneseName="コアドラモン（青）" ChineseName="核龙兽（蓝）">
        <Level DigimonLevel="成熟期"/>
        <Skills>
        </Skills>
    </Digimon>
    <Digimon JapaneseName="コアドラモン（緑）" ChineseName="核龙兽（绿）">
        <Level DigimonLevel="成熟期"/>
        <Skills>
        </Skills>
    </Digimon>
    <Digimon JapaneseName="ゴリモン" ChineseName="金刚兽">
        <Level DigimonLevel="成熟期"/>
        <Skills>
        </Skills>
    </Digimon>
    <Digimon JapaneseName="ソーラーモン" ChineseName="日轮兽">
        <Level DigimonLevel="成长期"/>
        <Skills>
        </Skills>
    </Digimon>
    <Digimon JapaneseName="サンドヤンマモン" ChineseName="沙地蜻蜓兽">
        <Level DigimonLevel="成熟期"/>
        <Skills>
        </Skills>
    </Digimon>
    <Digimon JapaneseName="キャロモン" ChineseName="弹力兽">
        <Level DigimonLevel="幼年期Ⅱ"/>
        <Skills>
        </Skills>
    </Digimon>
    <Digimon JapaneseName="ベアモン" ChineseName="小熊兽">
        <Level DigimonLevel="成长期"/>
        <Skills>
        </Skills>
    </Digimon>
    <Digimon JapaneseName="ラブラモン" ChineseName="拉布拉兽">
        <Level DigimonLevel="成长期"/>
        <Skills>
        </Skills>
    </Digimon>
    <Digimon JapaneseName="ネーモン" ChineseName="问答兽">
        <Level DigimonLevel="成长期"/>
        <Skills>
        </Skills>
    </Digimon>
    <Digimon JapaneseName="スコピオモン" ChineseName="毒蝎兽">
        <Level DigimonLevel="完全体"/>
        <Skills>
        </Skills>
    </Digimon>
    <Digimon JapaneseName="ファンビーモン" ChineseName="幻蜂兽">
        <Level DigimonLevel="成长期"/>
        <Skills>
            <Skill JapaneseName="ギアスティンガー" ChineseName="齿轮刺针"/>
        </Skills>
    </Digimon>
    <Digimon JapaneseName="ワスプモン" ChineseName="胡蜂兽">
        <Level DigimonLevel="成熟期"/>
        <Skills>
        </Skills>
    </Digimon>
    <Digimon JapaneseName="キャノンビーモン" ChineseName="炮蜂兽">
        <Level DigimonLevel="完全体"/>
        <Skills>
        </Skills>
    </Digimon>
    <Digimon JapaneseName="オオクワモン" ChineseName="大古加兽">
        <Level DigimonLevel="完全体"/>
        <Skills>
        </Skills>
    </Digimon>
    <Digimon JapaneseName="アイズモン" ChineseName="多目兽">
        <Level DigimonLevel="成熟期"/>
        <Skills>
            <Skill JapaneseName="愚幻" ChineseName="愚幻"/>
            <Skill JapaneseName="愚幻" ChineseName="邪念眼"/>
        </Skills>
    </Digimon>
    <Digimon JapaneseName="オロチモン" ChineseName="大蛇兽">
        <Level DigimonLevel="完全体"/>
        <Skills>
        </Skills>
    </Digimon>
    <Digimon JapaneseName="ニーズヘッグモン" ChineseName="尼德霍格兽">
        <Level DigimonLevel="究极体"/>
        <Skills>
        </Skills>
    </Digimon>
    <Digimon JapaneseName="バルブモン" ChineseName="阀门兽">
        <Level DigimonLevel="完全体"/>
        <Skills>
        </Skills>
    </Digimon>
    <Digimon JapaneseName="ミノタルモン" ChineseName="米诺陶兽">
        <Level DigimonLevel="完全体"/>
        <Skills>
        </Skills>
    </Digimon>
    <Digimon JapaneseName="ブルモン" ChineseName="公牛兽">
        <Level DigimonLevel="完全体"/>
        <Skills>
        </Skills>
    </Digimon>
    <Digimon JapaneseName="トレイルモン" ChineseName="机车兽">
        <Level DigimonLevel="成熟期"/>
        <Skills>
        </Skills>
    </Digimon>
    <Digimon JapaneseName="ボコモン" ChineseName="波高兽">
        <Level DigimonLevel="成长期"/>
        <Skills>
            <Skill JapaneseName="逃げ足猛ダッシュ" ChineseName="猛冲刺逃跑"/>
        </Skills>
    </Digimon>
    <Digimon JapaneseName="ケルベロモン" ChineseName="刻耳柏洛兽（沙路比兽）">
        <Level DigimonLevel="完全体"/>
        <Skills>
            <Skill JapaneseName="ヘルファイアー" ChineseName="地狱业火（地狱业焰）"/>
            <Skill JapaneseName="地狱业火（地狱业焰）" ChineseName="インフェルノゲート"/>
            <Skill JapaneseName="インフェルノディバイド" ChineseName="地狱分离"/>
        </Skills>
    </Digimon>
    <Digimon JapaneseName="アグニモン" ChineseName="火神兽">
        <Level DigimonLevel="混合体"/>
        <Skills>
            <Skill JapaneseName="サラマンダーブレイク" ChineseName="火龙飞踢"/>
            <Skill JapaneseName="火龙飞踢" ChineseName="バーニングサラマンダー"/>
            <Skill JapaneseName="ファイヤダーツ" ChineseName="火焰飞镖"/>
        </Skills>
    </Digimon>
    <Digimon JapaneseName="ヴォルフモン" ChineseName="野狼兽">
        <Level DigimonLevel="混合体"/>
        <Skills>
            <Skill JapaneseName="リヒト・ズィーガー" ChineseName="镭射剑击（光之胜利者）"/>
            <Skill JapaneseName="镭射剑击（光之胜利者）" ChineseName="リヒト・クーゲル"/>
            <Skill JapaneseName="ツヴァイ・ズィーガー" ChineseName="双重胜利者？"/>
        </Skills>
    </Digimon>
    <Digimon JapaneseName="ケルビモン" ChineseName="基路比兽（智天使兽）">
        <Level DigimonLevel="究极体"/>
        <Skills>
        </Skills>
    </Digimon>
    <Digimon JapaneseName="キャンドモン" ChineseName="蜡烛兽">
        <Level DigimonLevel="成长期"/>
        <Skills>
            <Skill JapaneseName="ボンファイア" ChineseName="篝火投射（篝火、暴热火焰）"/>
            <Skill JapaneseName="篝火投射（篝火、暴热火焰）" ChineseName="メルトワックス"/>
        </Skills>
    </Digimon>
    <Digimon JapaneseName="ルーチェモン" ChineseName="光明兽（六翅兽）">
        <Level DigimonLevel="成长期"/>
        <Skills>
        </Skills>
    </Digimon>
    <Digimon JapaneseName="チャックモン" ChineseName="冰熊兽">
        <Level DigimonLevel="混合体"/>
        <Skills>
            <Skill JapaneseName="カチカチコッチン" ChineseName="冰柱飞吹"/>
            <Skill JapaneseName="冰柱飞吹" ChineseName="ツララララ～"/>
            <Skill JapaneseName="スノーボンバー" ChineseName="雪球炮轰"/>
        </Skills>
    </Digimon>
    <Digimon JapaneseName="マッシュモン" ChineseName="蘑菇兽">
        <Level DigimonLevel="成长期"/>
        <Skills>
            <Skill JapaneseName="ポイズンスマッシュ" ChineseName="毒蘑菇扣杀"/>
        </Skills>
    </Digimon>
    <Digimon JapaneseName="フェアリモン" ChineseName="仙女兽">
        <Level DigimonLevel="混合体"/>
        <Skills>
            <Skill JapaneseName="トルナード・ガンバ" ChineseName="旋风腿"/>
            <Skill JapaneseName="旋风腿" ChineseName="ロゼオ・テンポラーレ"/>
        </Skills>
    </Digimon>
    <Digimon JapaneseName="ゴブリモン" ChineseName="哥布林兽">
        <Level DigimonLevel="成长期"/>
        <Skills>
        </Skills>
    </Digimon>
    <Digimon JapaneseName="ブリッツモン" ChineseName="电光兽">
        <Level DigimonLevel="混合体"/>
        <Skills>
            <Skill JapaneseName="トールハンマー" ChineseName="雷神重锤（托尔重锤、爆锤雷击）"/>
            <Skill JapaneseName="雷神重锤（托尔重锤、爆锤雷击）" ChineseName="ライトニング"/>
        </Skills>
    </Digimon>
    <Digimon JapaneseName="コクワモン" ChineseName="机甲虫兽（小锹形虫兽）">
        <Level DigimonLevel="成长期"/>
        <Skills>
        </Skills>
    </Digimon>
    <Digimon JapaneseName="グロットモン" ChineseName="洞窟兽（古洛顿兽）">
        <Level DigimonLevel="混合体"/>
        <Skills>
        </Skills>
    </Digimon>
    <Digimon JapaneseName="コンゴウモン" ChineseName="金刚杵兽">
        <Level DigimonLevel="装甲体"/>
        <Skills>
        </Skills>
    </Digimon>
    <Digimon JapaneseName="カラツキヌメモン" ChineseName="贝壳鼻涕兽（蜗牛兽）">
        <Level DigimonLevel="成熟期"/>
        <Skills>
        </Skills>
    </Digimon>
    <Digimon JapaneseName="ギガスモン" ChineseName="巨岩兽">
        <Level DigimonLevel="混合体"/>
        <Skills>
            <Skill JapaneseName="アースクェイク" ChineseName="地震"/>
            <Skill JapaneseName="地震" ChineseName="ハリケーンボンバー"/>
        </Skills>
    </Digimon>
    <Digimon JapaneseName="トイアグモン（黒）" ChineseName="玩具亚古兽（黑）">
        <Level DigimonLevel="成长期"/>
        <Skills>
            <Skill JapaneseName="トイフレイム" ChineseName="玩具火焰弹（玩具火焰）"/>
        </Skills>
    </Digimon>
    <Digimon JapaneseName="パンダモン" ChineseName="熊猫兽">
        <Level DigimonLevel="完全体"/>
        <Skills>
            <Skill JapaneseName="アニマルネイル" ChineseName="动物爪"/>
        </Skills>
    </Digimon>
    <Digimon JapaneseName="トイアグモン" ChineseName="玩具亚古兽">
        <Level DigimonLevel="成长期"/>
        <Skills>
        </Skills>
    </Digimon>
    <Digimon JapaneseName="カプリモン" ChineseName="卡普利兽">
        <Level DigimonLevel="幼年期Ⅱ"/>
        <Skills>
        </Skills>
    </Digimon>
    <Digimon JapaneseName="ヤーモン" ChineseName="也也兽">
        <Level DigimonLevel="幼年期Ⅱ"/>
        <Skills>
        </Skills>
    </Digimon>
    <Digimon JapaneseName="ジャリモン" ChineseName="沙砾兽">
        <Level DigimonLevel="幼年期Ⅰ"/>
        <Skills>
        </Skills>
    </Digimon>
    <Digimon JapaneseName="ゼリモン" ChineseName="果冻兽">
        <Level DigimonLevel="幼年期Ⅰ"/>
        <Skills>
        </Skills>
    </Digimon>
    <Digimon JapaneseName="バクモン" ChineseName="梦貘兽（食梦兽）">
        <Level DigimonLevel="成长期"/>
        <Skills>
            <Skill JapaneseName="ナイトメアシンドローム" ChineseName="噩梦症候群"/>
        </Skills>
    </Digimon>
    <Digimon JapaneseName="ガルムモン" ChineseName="银狼兽（加鲁姆兽）">
        <Level DigimonLevel="混合体"/>
        <Skills>
            <Skill JapaneseName="スピードスター" ChineseName="速度之星"/>
        </Skills>
    </Digimon>
    <Digimon JapaneseName="ヴリトラモン" ChineseName="炎龙兽">
        <Level DigimonLevel="混合体"/>
        <Skills>
        </Skills>
    </Digimon>
    <Digimon JapaneseName="ゴーレモン" ChineseName="高力兽">
        <Level DigimonLevel="成熟期"/>
        <Skills>
        </Skills>
    </Digimon>
    <Digimon JapaneseName="シャーマモン" ChineseName="萨满兽">
        <Level DigimonLevel="成长期"/>
        <Skills>
        </Skills>
    </Digimon>
    <Digimon JapaneseName="セピックモン" ChineseName="塞皮克兽">
        <Level DigimonLevel="装甲体"/>
        <Skills>
        </Skills>
    </Digimon>
    <Digimon JapaneseName="ラーナモン" ChineseName="拉娜兽">
        <Level DigimonLevel="混合体"/>
        <Skills>
        </Skills>
    </Digimon>
    <Digimon JapaneseName="メルキューレモン" ChineseName="水银镜兽（银镜兽、水银兽）">
        <Level DigimonLevel="混合体"/>
        <Skills>
        </Skills>
    </Digimon>
    <Digimon JapaneseName="アルボルモン" ChineseName="怪树兽（圣树兽）">
        <Level DigimonLevel="混合体"/>
        <Skills>
            <Skill JapaneseName="マシンガン・ダンス" ChineseName="机关枪之舞"/>
        </Skills>
    </Digimon>
    <Digimon JapaneseName="ダスクモン" ChineseName="幽暗兽（暗黑兽）">
        <Level DigimonLevel="混合体"/>
        <Skills>
        </Skills>
    </Digimon>
    <Digimon JapaneseName="ソーサリモン" ChineseName="术师兽（冰巫师兽）">
        <Level DigimonLevel="成熟期"/>
        <Skills>
        </Skills>
    </Digimon>
    <Digimon JapaneseName="スカルナイトモン" ChineseName="骷髅骑士兽">
        <Level DigimonLevel="成熟期"/>
        <Skills>
        </Skills>
    </Digimon>
    <Digimon JapaneseName="エルドラディモン" ChineseName="要塞兽">
        <Level DigimonLevel="究极体"/>
        <Skills>
        </Skills>
    </Digimon>
    <Digimon JapaneseName="ダークメイルドラモン" ChineseName="黑暗铠龙兽">
        <Level DigimonLevel="成熟期"/>
        <Skills>
        </Skills>
    </Digimon>
    <Digimon JapaneseName="スプラッシュモン" ChineseName="激流兽">
        <Level DigimonLevel="完全体"/>
        <Skills>
            <Skill JapaneseName="ポイゾナスフォース" ChineseName="恶毒部众"/>
            <Skill JapaneseName="恶毒部众" ChineseName="ハイドロプレッシャー"/>
            <Skill JapaneseName="ビードラウン" ChineseName="水珠溺杀"/>
            <Skill JapaneseName="タイガータイフーン" ChineseName="水虎台风"/>
        </Skills>
    </Digimon>
    <Digimon JapaneseName="カルマーラモン" ChineseName="卡玛拉兽">
        <Level DigimonLevel="混合体"/>
        <Skills>
            <Skill JapaneseName="ネーロコルソ" ChineseName="黑色追逐"/>
            <Skill JapaneseName="黑色追逐" ChineseName="タイタニックチャージ"/>
        </Skills>
    </Digimon>
    <Digimon JapaneseName="チクリモン" ChineseName="刺针兽">
        <Level DigimonLevel="成长期"/>
        <Skills>
        </Skills>
    </Digimon>
    <Digimon JapaneseName="ネオデビモン" ChineseName="新种恶魔兽">
        <Level DigimonLevel="完全体"/>
        <Skills>
        </Skills>
    </Digimon>
    <Digimon JapaneseName="ダンデビモン" ChineseName="但丁恶魔兽">
        <Level DigimonLevel="究极体"/>
        <Skills>
        </Skills>
    </Digimon>
    <Digimon JapaneseName="マメモン" ChineseName="豆豆兽">
        <Level DigimonLevel="完全体"/>
        <Skills>
        </Skills>
    </Digimon>
    <Digimon JapaneseName="ズルモン" ChineseName="狡猾兽">
        <Level DigimonLevel="幼年期Ⅰ"/>
        <Skills>
        </Skills>
    </Digimon>
    <Digimon JapaneseName="グラウンドラモン" ChineseName="地龙兽">
        <Level DigimonLevel="完全体"/>
        <Skills>
        </Skills>
    </Digimon>
    <Digimon JapaneseName="エビドラモン" ChineseName="龙虾兽">
        <Level DigimonLevel="成熟期"/>
        <Skills>
        </Skills>
    </Digimon>
    <Digimon JapaneseName="ワルシードラモン" ChineseName="恶海龙兽">
        <Level DigimonLevel="完全体"/>
        <Skills>
        </Skills>
    </Digimon>
    <Digimon JapaneseName="ペックモン" ChineseName="啄木鸟兽">
        <Level DigimonLevel="成熟期"/>
        <Skills>
        </Skills>
    </Digimon>
    <Digimon JapaneseName="トータモン" ChineseName="陆龟兽">
        <Level DigimonLevel="成熟期"/>
        <Skills>
        </Skills>
    </Digimon>
    <Digimon JapaneseName="ビッグマメモン" ChineseName="巨大豆豆兽">
        <Level DigimonLevel="完全体"/>
        <Skills>
        </Skills>
    </Digimon>
    <Digimon JapaneseName="ヴォルクドラモン" ChineseName="火山龙兽">
        <Level DigimonLevel="完全体"/>
        <Skills>
        </Skills>
    </Digimon>
    <Digimon JapaneseName="サイバードラモン" ChineseName="科学飞龙兽">
        <Level DigimonLevel="完全体"/>
        <Skills>
        </Skills>
    </Digimon>
    <Digimon JapaneseName="デッカードラモン" ChineseName="军舰龙兽">
        <Level DigimonLevel="成熟期"/>
        <Skills>
        </Skills>
    </Digimon>
    <Digimon JapaneseName="タンクドラモン" ChineseName="坦克龙兽">
        <Level DigimonLevel="完全体"/>
        <Skills>
        </Skills>
    </Digimon>
    <Digimon JapaneseName="ロップモン" ChineseName="黑大耳兽">
        <Level DigimonLevel="成长期"/>
        <Skills>
            <Skill JapaneseName="プチツイスター" ChineseName="小龙卷"/>
            <Skill JapaneseName="小龙卷" ChineseName="ダブルタイフーン"/>
            <Skill JapaneseName="ブレイジングアイス" ChineseName="炽烈寒冰"/>
        </Skills>
    </Digimon>
    <Digimon JapaneseName="バドモン" ChineseName="花蕾兽">
        <Level DigimonLevel="成长期"/>
        <Skills>
        </Skills>
    </Digimon>
    <Digimon JapaneseName="アロモン" ChineseName="异龙兽">
        <Level DigimonLevel="装甲体"/>
        <Skills>
        </Skills>
    </Digimon>
    <Digimon JapaneseName="コモンドモン " ChineseName="拖把狗兽">
        <Level DigimonLevel="成熟期"/>
        <Skills>
        </Skills>
    </Digimon>
    <Digimon JapaneseName="ゴクモン" ChineseName="狱门兽">
        <Level DigimonLevel="完全体"/>
        <Skills>
        </Skills>
    </Digimon>
    <Digimon JapaneseName="メタルファントモン" ChineseName="金属死神兽">
        <Level DigimonLevel="完全体"/>
        <Skills>
            <Skill JapaneseName="ソウルプレデター" ChineseName="灵魂掠夺"/>
            <Skill JapaneseName="灵魂掠夺" ChineseName="グレイブスクリーム"/>
        </Skills>
    </Digimon>
    <Digimon JapaneseName="ミレニアモン" ChineseName="千年兽">
        <Level DigimonLevel="幼年期Ⅰ"/>
        <Skills>
        </Skills>
    </Digimon>
    <Digimon JapaneseName="ペガスモン" ChineseName="天马兽">
        <Level DigimonLevel="装甲体"/>
        <Skills>
            <Skill JapaneseName="シルバーブレイズ" ChineseName="银色光芒"/>
            <Skill JapaneseName="银色光芒" ChineseName="ロデオギャロップ"/>
        </Skills>
    </Digimon>
    <Digimon JapaneseName="マンボモン" ChineseName="翻车鲀兽">
        <Level DigimonLevel="装甲体"/>
        <Skills>
        </Skills>
    </Digimon>
    <Digimon JapaneseName="シーホモン" ChineseName="海马兽">
        <Level DigimonLevel="装甲体"/>
        <Skills>
        </Skills>
    </Digimon>
    <Digimon JapaneseName="マンタレイモン" ChineseName="蝠鲼兽">
        <Level DigimonLevel="装甲体"/>
        <Skills>
        </Skills>
    </Digimon>
    <Digimon JapaneseName="マリンエンジェモン" ChineseName="海天使兽">
        <Level DigimonLevel="究极体"/>
        <Skills>
            <Skill JapaneseName="オーシャンラブ" ChineseName="海洋之爱"/>
        </Skills>
    </Digimon>
    <Digimon JapaneseName="ダイペンモン" ChineseName="大企鹅兽">
        <Level DigimonLevel="混合体"/>
        <Skills>
            <Skill JapaneseName="ブルーハワイデス" ChineseName="蓝色夏威夷死亡"/>
            <Skill JapaneseName="蓝色夏威夷死亡" ChineseName="イチゴデス"/>
        </Skills>
    </Digimon>
    <Digimon JapaneseName="ブレイドクワガーモン" ChineseName="刃古加兽">
        <Level DigimonLevel="成熟期"/>
        <Skills>
        </Skills>
    </Digimon>
    <Digimon JapaneseName="グソクモン" ChineseName="具足兽">
        <Level DigimonLevel="完全体"/>
        <Skills>
        </Skills>
    </Digimon>
    <Digimon JapaneseName="メタリフェクワガーモン" ChineseName="美他利佛古加兽">
        <Level DigimonLevel="完全体"/>
        <Skills>
        </Skills>
    </Digimon>
    <Digimon JapaneseName="スナリザモン" ChineseName="沙蜥蜴兽">
        <Level DigimonLevel="成长期"/>
        <Skills>
            <Skill JapaneseName="サンドブラスト" ChineseName="狂沙暴风"/>
        </Skills>
    </Digimon>
    <Digimon JapaneseName="ゴグマモン" ChineseName="戈格马兽">
        <Level DigimonLevel="完全体"/>
        <Skills>
        </Skills>
    </Digimon>
    <Digimon JapaneseName="メフィスモン" ChineseName="梅菲斯兽">
        <Level DigimonLevel="完全体"/>
        <Skills>
        </Skills>
    </Digimon>
    <Digimon JapaneseName="エルドラディモン　" ChineseName="要塞兽">
        <Level DigimonLevel="究极体"/>
        <Skills>
        </Skills>
    </Digimon>
    <Digimon JapaneseName="ポテモン" ChineseName="薯条兽">
        <Level DigimonLevel="成熟期"/>
        <Skills>
        </Skills>
    </Digimon>
    <Digimon JapaneseName="ルナモン" ChineseName="露娜兽">
        <Level DigimonLevel="成长期"/>
        <Skills>
            <Skill JapaneseName="ロップイヤーリップル" ChineseName="垂耳兔波动"/>
        </Skills>
    </Digimon>
    <Digimon JapaneseName="ジャガモン" ChineseName="马铃薯兽">
        <Level DigimonLevel="完全体"/>
        <Skills>
        </Skills>
    </Digimon>
    <Digimon JapaneseName="バーガモン" ChineseName="汉堡兽">
        <Level DigimonLevel="成长期"/>
        <Skills>
            <Skill JapaneseName="グリーンピクルス" ChineseName="酸黄瓜"/>
            <Skill JapaneseName="酸黄瓜" ChineseName="デリシャスパティ"/>
        </Skills>
    </Digimon>
    <Digimon JapaneseName="トリカラボールモン" ChineseName="鸡块兽">
        <Level DigimonLevel="幼年期Ⅱ"/>
        <Skills>
        </Skills>
    </Digimon>
    <Digimon JapaneseName="クネモン" ChineseName="古尼兽">
        <Level DigimonLevel="成长期"/>
        <Skills>
        </Skills>
    </Digimon>
    <Digimon JapaneseName="カメモン" ChineseName="小乌龟兽">
        <Level DigimonLevel="成长期"/>
        <Skills>
        </Skills>
    </Digimon>
    <Digimon JapaneseName="トロピアモン" ChineseName="热带兽">
        <Level DigimonLevel="完全体"/>
        <Skills>
            <Skill JapaneseName="ペタリーカーネイジ" ChineseName="花瓣杀戮"/>
            <Skill JapaneseName="花瓣杀戮" ChineseName="トロピカルヴェノム"/>
        </Skills>
    </Digimon>
    <Digimon JapaneseName="ポームモン" ChineseName="水果兽">
        <Level DigimonLevel="成长期"/>
        <Skills>
        </Skills>
    </Digimon>
    <Digimon JapaneseName="オポッサモン" ChineseName="负鼠兽">
        <Level DigimonLevel="装甲体"/>
        <Skills>
        </Skills>
    </Digimon>
    <Digimon JapaneseName="フリモン" ChineseName="皱褶兽">
        <Level DigimonLevel="幼年期Ⅱ"/>
        <Skills>
        </Skills>
    </Digimon>
    <Digimon JapaneseName="プロロモン" ChineseName="普罗罗兽">
        <Level DigimonLevel="幼年期Ⅱ"/>
        <Skills>
        </Skills>
    </Digimon>
    <Digimon JapaneseName="サーチモン" ChineseName="搜索兽">
        <Level DigimonLevel="装甲体"/>
        <Skills>
        </Skills>
    </Digimon>
    <Digimon JapaneseName="レアレアモン" ChineseName="超烂泥兽">
        <Level DigimonLevel="完全体"/>
        <Skills>
        </Skills>
    </Digimon>
    <Digimon JapaneseName="マリンデビモン" ChineseName="海恶魔兽">
        <Level DigimonLevel="完全体"/>
        <Skills>
        </Skills>
    </Digimon>
    <Digimon JapaneseName="ブリッツグレイモン" ChineseName="电光暴龙兽">
        <Level DigimonLevel="究极体"/>
        <Skills>
        </Skills>
    </Digimon>
    <Digimon JapaneseName="プスリモン" ChineseName="普斯利兽">
        <Level DigimonLevel="幼年期Ⅱ"/>
        <Skills>
        </Skills>
    </Digimon>
    <Digimon JapaneseName="ブリンプモン" ChineseName="飞艇兽">
        <Level DigimonLevel="成熟期"/>
        <Skills>
        </Skills>
    </Digimon>
    <Digimon JapaneseName="チビックモン" ChineseName="小拨片兽">
        <Level DigimonLevel="幼年期Ⅰ"/>
        <Skills>
        </Skills>
    </Digimon>
    <Digimon JapaneseName="チョロモン" ChineseName="巧洛兽">
        <Level DigimonLevel="幼年期Ⅰ"/>
        <Skills>
        </Skills>
    </Digimon>
    <Digimon JapaneseName="シャオモン" ChineseName="小小兽">
        <Level DigimonLevel="幼年期Ⅱ"/>
        <Skills>
        </Skills>
    </Digimon>
    <Digimon JapaneseName="ポンチョモン" ChineseName="雨披兽">
        <Level DigimonLevel="装甲体"/>
        <Skills>
        </Skills>
    </Digimon>
    <Digimon JapaneseName="ボルケーモン" ChineseName="火山兽">
        <Level DigimonLevel="完全体"/>
        <Skills>
        </Skills>
    </Digimon>
    <Digimon JapaneseName="バーガモン" ChineseName="汉堡兽">
        <Level DigimonLevel="成长期"/>
        <Skills>
            <Skill JapaneseName="デリシャスパティ" ChineseName="美味肉饼"/>
            <Skill JapaneseName="美味肉饼" ChineseName="グリーンピクルス"/>
        </Skills>
    </Digimon>
    <Digimon JapaneseName="ペタルドラモン" ChineseName="花龙兽">
        <Level DigimonLevel="混合体"/>
        <Skills>
            <Skill JapaneseName="デリシャスパティ" ChineseName="树叶旋风"/>
            <Skill JapaneseName="树叶旋风" ChineseName="サウザンドスパイク"/>
        </Skills>
    </Digimon>
    <Digimon JapaneseName="エントモン" ChineseName="树虫兽">
        <Level DigimonLevel="完全体"/>
        <Skills>
            <Skill JapaneseName="ドライアドスティンガー" ChineseName="德律阿得斯刺钉"/>
            <Skill JapaneseName="德律阿得斯刺钉" ChineseName="ブラステッドディザスター"/>
        </Skills>
    </Digimon>
    <Digimon JapaneseName="プワモン" ChineseName="普瓦兽">
        <Level DigimonLevel="幼年期Ⅰ"/>
        <Skills>
            <Skill JapaneseName="フワーフェザー" ChineseName="柔羽"/>
        </Skills>
    </Digimon>
    <Digimon JapaneseName="ムーチョモン" ChineseName="五彩兽">
        <Level DigimonLevel="成长期"/>
        <Skills>
            <Skill JapaneseName="トロピカルビーク" ChineseName="热带喙啄"/>
        </Skills>
    </Digimon>
    <Digimon JapaneseName="マッハモン" ChineseName="音速兽">
        <Level DigimonLevel="成熟期"/>
        <Skills>
            <Skill JapaneseName="マッドネスファイア" ChineseName="疯狂射击"/>
            <Skill JapaneseName="疯狂射击" ChineseName="フルスロットルエッジ"/>
        </Skills>
    </Digimon>
    <Digimon JapaneseName="パラサイモン" ChineseName="寄生兽">
        <Level DigimonLevel="究极体"/>
        <Skills>
        </Skills>
    </Digimon>
    <Digimon JapaneseName="セフィロトモン" ChineseName="魔弹兽">
        <Level DigimonLevel="混合体"/>
        <Skills>
        </Skills>
    </Digimon>
    <Digimon JapaneseName="ノヘモン" ChineseName="稻草人兽">
        <Level DigimonLevel="装甲体"/>
        <Skills>
        </Skills>
    </Digimon>
    <Digimon JapaneseName="ガオスモン" ChineseName="气龙兽">
        <Level DigimonLevel="成长期"/>
        <Skills>
        </Skills>
    </Digimon>
    <Digimon JapaneseName="ミニデカチモン" ChineseName="迷你大头兽">
        <Level DigimonLevel="成长期"/>
        <Skills>
        </Skills>
    </Digimon>
    <Digimon JapaneseName="アタマデカチモン" ChineseName="大头兽">
        <Level DigimonLevel="成熟期"/>
        <Skills>
        </Skills>
    </Digimon>
    <Digimon JapaneseName="ギロモン" ChineseName="机雷兽">
        <Level DigimonLevel="完全体"/>
        <Skills>
        </Skills>
    </Digimon>
    <Digimon JapaneseName="リベリモン" ChineseName="叛逆兽">
        <Level DigimonLevel="完全体"/>
        <Skills>
        </Skills>
    </Digimon>
    <Digimon JapaneseName="ボルトモン" ChineseName="螺栓兽">
        <Level DigimonLevel="究极体"/>
        <Skills>
        </Skills>
    </Digimon>
    <Digimon JapaneseName="キュートモン" ChineseName="萌萌兽">
        <Level DigimonLevel="成长期"/>
        <Skills>
        </Skills>
    </Digimon>
    <Digimon JapaneseName="ボアモン" ChineseName="野猪兽">
        <Level DigimonLevel="装甲体"/>
        <Skills>
        </Skills>
    </Digimon>
    <Digimon JapaneseName="テッカモン" ChineseName="铁面兽">
        <Level DigimonLevel="完全体"/>
        <Skills>
        </Skills>
    </Digimon>
    <Digimon JapaneseName="ババモン" ChineseName="婆婆兽">
        <Level DigimonLevel="究极体"/>
        <Skills>
            <Skill JapaneseName="エンプレスヘイズ" ChineseName="皇后阴霾"/>
        </Skills>
    </Digimon>
    <Digimon JapaneseName="ララモン" ChineseName="拉拉兽">
        <Level DigimonLevel="成长期"/>
        <Skills>
        </Skills>
    </Digimon>
    <Digimon JapaneseName="ジジモン" ChineseName="公公兽">
        <Level DigimonLevel="究极体"/>
        <Skills>
        </Skills>
    </Digimon>
    <Digimon JapaneseName="バンチョーマメモン" ChineseName="番长豆豆兽">
        <Level DigimonLevel="究极体"/>
        <Skills>
        </Skills>
    </Digimon>
    <Digimon JapaneseName="ザンバモン" ChineseName="斩伐兽">
        <Level DigimonLevel="究极体"/>
        <Skills>
        </Skills>
    </Digimon>
    <Digimon JapaneseName="グリズモン" ChineseName="灰熊兽">
        <Level DigimonLevel="成熟期"/>
        <Skills>
        </Skills>
    </Digimon>
    <Digimon JapaneseName="ストラビモン" ChineseName="闪光兽">
        <Level DigimonLevel="混合体"/>
        <Skills>
        </Skills>
    </Digimon>
    <Digimon JapaneseName="ハヌモン" ChineseName="哈努兽">
        <Level DigimonLevel="成熟期"/>
        <Skills>
        </Skills>
    </Digimon>
    <Digimon JapaneseName="クーレスガルルモン" ChineseName="偃月加鲁鲁兽">
        <Level DigimonLevel="究极体"/>
        <Skills>
        </Skills>
    </Digimon>
    <Digimon JapaneseName="ソウルモン" ChineseName="鬼魂兽">
        <Level DigimonLevel="成熟期"/>
        <Skills>
        </Skills>
    </Digimon>
    <Digimon JapaneseName="ワイズモン" ChineseName="贤者兽">
        <Level DigimonLevel="完全体"/>
        <Skills>
        </Skills>
    </Digimon>
    <Digimon JapaneseName="ガンマモン" ChineseName="伽马兽">
        <Level DigimonLevel="成长期"/>
        <Skills>
            <Skill JapaneseName="ブレイクロー" ChineseName="破坏利爪"/>
            <Skill JapaneseName="破坏利爪" ChineseName="ホーンアタック"/>
        </Skills>
    </Digimon>
    <Digimon JapaneseName="アンゴラモン" ChineseName="安哥拉兽">
        <Level DigimonLevel="成长期"/>
        <Skills>
            <Skill JapaneseName="ダブルラリアット" ChineseName="双重套索"/>
            <Skill JapaneseName="双重套索" ChineseName="ピョンダンプ"/>
            <Skill JapaneseName="プチトルネード" ChineseName="小型龙卷"/>
        </Skills>
    </Digimon>
    <Digimon JapaneseName="ジェリーモン" ChineseName="海蜇兽">
        <Level DigimonLevel="成长期"/>
        <Skills>
            <Skill JapaneseName="ビビサンダー" ChineseName="麻痹雷击"/>
            <Skill JapaneseName="麻痹雷击" ChineseName="ボルトナックル"/>
            <Skill JapaneseName="スパイラルキック" ChineseName="螺旋飞踢"/>
        </Skills>
    </Digimon>
    <Digimon JapaneseName="クロックモン" ChineseName="时钟兽">
        <Level DigimonLevel="成熟期"/>
        <Skills>
            <Skill JapaneseName="クロノブレーカー" ChineseName="时空破坏者"/>
        </Skills>
    </Digimon>
    <Digimon JapaneseName="マミーモン" ChineseName="木乃伊兽">
        <Level DigimonLevel="完全体"/>
        <Skills>
        </Skills>
    </Digimon>
    <Digimon JapaneseName="ベテルガンマモン" ChineseName="参宿四伽马兽">
        <Level DigimonLevel="成熟期"/>
        <Skills>
            <Skill JapaneseName="ソルショット" ChineseName="太阳射击"/>
            <Skill JapaneseName="太阳射击" ChineseName="ソルブロー"/>
        </Skills>
    </Digimon>
    <Digimon JapaneseName="ドラクモン" ChineseName="德拉库兽">
        <Level DigimonLevel="成长期"/>
        <Skills>
        </Skills>
    </Digimon>
    <Digimon JapaneseName="エカキモン" ChineseName="画家兽">
        <Level DigimonLevel="成长期"/>
        <Skills>
            <Skill JapaneseName="カラフルチェンジ" ChineseName="多彩变化"/>
        </Skills>
    </Digimon>
    <Digimon JapaneseName="マジラモン" ChineseName="天龙兽">
        <Level DigimonLevel="完全体"/>
        <Skills>
            <Skill JapaneseName="ヴェーダカ" ChineseName="刺穿"/>
        </Skills>
    </Digimon>
    <Digimon JapaneseName="クアトルモン" ChineseName="羽蛇兽">
        <Level DigimonLevel="装甲体"/>
        <Skills>
        </Skills>
    </Digimon>
    <Digimon JapaneseName="ビットモン" ChineseName="兔仔兽">
        <Level DigimonLevel="装甲体"/>
        <Skills>
        </Skills>
    </Digimon>
    <Digimon JapaneseName="ゴートモン" ChineseName="山羊兽">
        <Level DigimonLevel="装甲体"/>
        <Skills>
        </Skills>
    </Digimon>
    <Digimon JapaneseName="ヨウコモン" ChineseName="狐妖兽">
        <Level DigimonLevel="成熟期"/>
        <Skills>
        </Skills>
    </Digimon>
    <Digimon JapaneseName="セイレーンモン" ChineseName="塞壬兽">
        <Level DigimonLevel="完全体"/>
        <Skills>
            <Skill JapaneseName="第一曲≪ポリフォニー≫" ChineseName="第一曲《复调》"/>
            <Skill JapaneseName="第一曲《复调》" ChineseName="第二曲≪アリア≫"/>
            <Skill JapaneseName="第三曲≪カノン≫" ChineseName="第三曲《卡农》"/>
        </Skills>
    </Digimon>
    <Digimon JapaneseName="ヤタガラモン" ChineseName="八咫乌兽">
        <Level DigimonLevel="完全体"/>
        <Skills>
            <Skill JapaneseName="甕布都神" ChineseName="瓮布都神"/>
            <Skill JapaneseName="瓮布都神" ChineseName="羽黒"/>
        </Skills>
    </Digimon>
    <Digimon JapaneseName="カウスガンマモン" ChineseName="箕宿三伽马兽">
        <Level DigimonLevel="成熟期"/>
        <Skills>
            <Skill JapaneseName="ウルダインパルス" ChineseName="乌尔德脉冲"/>
            <Skill JapaneseName="乌尔德脉冲" ChineseName="ランベルタキック"/>
        </Skills>
    </Digimon>
    <Digimon JapaneseName="シスタモン シエル" ChineseName="修女兽 天蓝">
        <Level DigimonLevel="成熟期"/>
        <Skills>
            <Skill JapaneseName="白詰一文字切り" ChineseName="白诘一文字切"/>
            <Skill JapaneseName="白诘一文字切" ChineseName="白殺"/>
            <Skill JapaneseName="突蜂" ChineseName="突蜂"/>
        </Skills>
    </Digimon>
    <Digimon JapaneseName="キンカクモン" ChineseName="金角兽">
        <Level DigimonLevel="成熟期"/>
        <Skills>
        </Skills>
    </Digimon>
    <Digimon JapaneseName="ギンカクモン" ChineseName="银角兽">
        <Level DigimonLevel="成熟期"/>
        <Skills>
        </Skills>
    </Digimon>
    <Digimon JapaneseName="テスラジェリーモン" ChineseName="特斯拉海蜇兽">
        <Level DigimonLevel="成熟期"/>
        <Skills>
            <Skill JapaneseName="フィサリスト" ChineseName="霹雳重拳"/>
            <Skill JapaneseName="霹雳重拳" ChineseName="パニッシューネ"/>
            <Skill JapaneseName="ボルスプライト" ChineseName="精灵电击"/>
        </Skills>
    </Digimon>
    <Digimon JapaneseName="レッパモン" ChineseName="裂破兽">
        <Level DigimonLevel="成熟期"/>
        <Skills>
            <Skill JapaneseName="獣牙乱撃" ChineseName="兽牙乱击"/>
        </Skills>
    </Digimon>
    <Digimon JapaneseName="ザッソーモン" ChineseName="杂草兽">
        <Level DigimonLevel="成熟期"/>
        <Skills>
            <Skill JapaneseName="スクイーズバイン" ChineseName="压榨藤蔓"/>
        </Skills>
    </Digimon>
    <Digimon JapaneseName="ウェズンガンマモン" ChineseName="弧矢一伽马兽">
        <Level DigimonLevel="成熟期"/>
        <Skills>
            <Skill JapaneseName="セドナ" ChineseName="赛德娜炮击"/>
            <Skill JapaneseName="赛德娜炮击" ChineseName="アルビオン"/>
        </Skills>
    </Digimon>
    <Digimon JapaneseName="サラマンダモン" ChineseName="火蝾螈兽">
        <Level DigimonLevel="装甲体"/>
        <Skills>
            <Skill JapaneseName="バックドラフト" ChineseName="回燃"/>
            <Skill JapaneseName="回燃" ChineseName="ヒートブレス"/>
        </Skills>
    </Digimon>
    <Digimon JapaneseName="シールズドラモン" ChineseName="海豹龙兽">
        <Level DigimonLevel="成熟期"/>
        <Skills>
            <Skill JapaneseName="デスビハインド" ChineseName="死亡背刺"/>
            <Skill JapaneseName="死亡背刺" ChineseName="スカウターモノアイ"/>
        </Skills>
    </Digimon>
    <Digimon JapaneseName="グルスガンマモン" ChineseName="轩辕十四伽马兽">
        <Level DigimonLevel="成熟期"/>
        <Skills>
            <Skill JapaneseName="デッドエンドスキュアー" ChineseName="终结穿刺"/>
            <Skill JapaneseName="终结穿刺" ChineseName="デスデモーナ"/>
            <Skill JapaneseName="ダークパレス" ChineseName="黑暗帕勒斯"/>
        </Skills>
    </Digimon>
    <Digimon JapaneseName="コエモン" ChineseName="小猴兽">
        <Level DigimonLevel="成长期"/>
        <Skills>
            <Skill JapaneseName="ミスチバスフープ" ChineseName="恶作剧之环"/>
            <Skill JapaneseName="恶作剧之环" ChineseName="ベビースリング"/>
        </Skills>
    </Digimon>
    <Digimon JapaneseName="ブギーモン" ChineseName="魔鬼兽">
        <Level DigimonLevel="成熟期"/>
        <Skills>
        </Skills>
    </Digimon>
    <Digimon JapaneseName="ジンバーアンゴラモン" ChineseName="阵羽安哥拉兽">
        <Level DigimonLevel="成熟期"/>
        <Skills>
            <Skill JapaneseName="レントライザー" ChineseName="旋耳龙卷"/>
            <Skill JapaneseName="旋耳龙卷" ChineseName="ブレイキンストリーム"/>
            <Skill JapaneseName="ジャイブ" ChineseName="捷舞"/>
        </Skills>
    </Digimon>
    <Digimon JapaneseName="フェレスモン" ChineseName="费勒斯兽">
        <Level DigimonLevel="完全体"/>
        <Skills>
            <Skill JapaneseName="ブラックスタチュー" ChineseName="黑色雕像"/>
            <Skill JapaneseName="黑色雕像" ChineseName="デーモンズシャウト"/>
        </Skills>
    </Digimon>
    <Digimon JapaneseName="モリシェルモン" ChineseName="森林贝壳兽">
        <Level DigimonLevel="成熟期"/>
        <Skills>
        </Skills>
    </Digimon>
    <Digimon JapaneseName="フロゾモン" ChineseName="冰象兽">
        <Level DigimonLevel="完全体"/>
        <Skills>
            <Skill JapaneseName="リムーバルブロウ" ChineseName="清除强击"/>
            <Skill JapaneseName="清除强击" ChineseName="デフロストブレード"/>
            <Skill JapaneseName="グラシエイトミサイル" ChineseName="冰冻导弹"/>
        </Skills>
    </Digimon>
    <Digimon JapaneseName="ピーターモン" ChineseName="彼得兽">
        <Level DigimonLevel="成熟期"/>
        <Skills>
            <Skill JapaneseName="スナイプスティング" ChineseName="狙击刺杀"/>
            <Skill JapaneseName="狙击刺杀" ChineseName="トゥインクルシュート"/>
            <Skill JapaneseName="ミッドナイトファンタジア" ChineseName="午夜幻想曲"/>
        </Skills>
    </Digimon>
    <Digimon JapaneseName="オルカモン" ChineseName="虎鲸兽">
        <Level DigimonLevel="装甲体"/>
        <Skills>
        </Skills>
    </Digimon>
    <Digimon JapaneseName="サンダーボールモン" ChineseName="雷电球兽">
        <Level DigimonLevel="成熟期"/>
        <Skills>
        </Skills>
    </Digimon>
    <Digimon JapaneseName="キャプテンフックモン" ChineseName="铁钩船长兽">
        <Level DigimonLevel="完全体"/>
        <Skills>
        </Skills>
    </Digimon>
    <Digimon JapaneseName="ダークリザモン" ChineseName="黑暗蜥蜴兽">
        <Level DigimonLevel="成熟期"/>
        <Skills>
            <Skill JapaneseName="ドレッドファイア" ChineseName="恐惧火焰"/>
        </Skills>
    </Digimon>
    <Digimon JapaneseName="セーバードラモン" ChineseName="黑巴多拉兽">
        <Level DigimonLevel="成熟期"/>
        <Skills>
            <Skill JapaneseName="ブラックセーバー" ChineseName="黑刃"/>
        </Skills>
    </Digimon>
    <Digimon JapaneseName="ブラックテイルモン" ChineseName="黑迪路兽">
        <Level DigimonLevel="成熟期"/>
        <Skills>
        </Skills>
    </Digimon>
    <Digimon JapaneseName="アルケニモン" ChineseName="亚基利兽">
        <Level DigimonLevel="完全体"/>
        <Skills>
            <Skill JapaneseName="スパイダースレッド" ChineseName="蜘蛛丝线"/>
            <Skill JapaneseName="蜘蛛丝线" ChineseName="プレデーションスパイダー"/>
        </Skills>
    </Digimon>
    <Digimon JapaneseName="ピロモン" ChineseName="枕头兽">
        <Level DigimonLevel="成长期"/>
        <Skills>
            <Skill JapaneseName="ララバイバブル" ChineseName="催眠曲泡泡"/>
            <Skill JapaneseName="催眠曲泡泡" ChineseName="悪夢の泡"/>
        </Skills>
    </Digimon>
    <Digimon JapaneseName="モルフォモン" ChineseName="闪蝶兽">
        <Level DigimonLevel="成长期"/>
        <Skills>
            <Skill JapaneseName="リンリンテラピー" ChineseName="唧唧治愈"/>
        </Skills>
    </Digimon>
    <Digimon JapaneseName="アヤタラモン" ChineseName="阿杰特兽">
        <Level DigimonLevel="完全体"/>
        <Skills>
            <Skill JapaneseName="アサルトハチェット" ChineseName="突袭劈刀"/>
            <Skill JapaneseName="突袭劈刀" ChineseName="タイドアップアイビー"/>
            <Skill JapaneseName="ショットガンモス" ChineseName="猎枪苔藓"/>
        </Skills>
    </Digimon>
    <Digimon JapaneseName="サングルゥモン" ChineseName="血狼兽">
        <Level DigimonLevel="成熟期"/>
        <Skills>
        </Skills>
    </Digimon>
    <Digimon JapaneseName="マタドゥルモン" ChineseName="斗牛士兽">
        <Level DigimonLevel="完全体"/>
        <Skills>
        </Skills>
    </Digimon>
    <Digimon JapaneseName="カノーヴァイスモン" ChineseName="卡诺维斯兽">
        <Level DigimonLevel="完全体"/>
        <Skills>
            <Skill JapaneseName="ドラゴニア" ChineseName="德拉贡尼亚"/>
            <Skill JapaneseName="德拉贡尼亚" ChineseName="ガリアフィッシャー"/>
            <Skill JapaneseName="メテオルクス" ChineseName="亡神流星"/>
            <Skill JapaneseName="グランノヴァ" ChineseName="宏伟新星"/>
        </Skills>
    </Digimon>
    <Digimon JapaneseName="アシュラモン" ChineseName="阿修罗兽">
        <Level DigimonLevel="完全体"/>
        <Skills>
        </Skills>
    </Digimon>
    <Digimon JapaneseName="コドクグモン" ChineseName="小毒蜘蛛兽">
        <Level DigimonLevel="成长期"/>
        <Skills>
        </Skills>
    </Digimon>
    <Digimon JapaneseName="エリスモン" ChineseName="刺猬兽">
        <Level DigimonLevel="成长期"/>
        <Skills>
        </Skills>
    </Digimon>
    <Digimon JapaneseName="テティスモン" ChineseName="忒提斯兽">
        <Level DigimonLevel="完全体"/>
        <Skills>
            <Skill JapaneseName="アドゥワールド" ChineseName="告别世界"/>
            <Skill JapaneseName="告别世界" ChineseName="ドクテアーゼ"/>
            <Skill JapaneseName="ビリースマッシャー" ChineseName="麻痹粉碎者"/>
            <Skill JapaneseName="ハンマーサンダー" ChineseName="重锤轰雷"/>
        </Skills>
    </Digimon>
    <Digimon JapaneseName="エクスティラノモン" ChineseName="EX巨龙兽">
        <Level DigimonLevel="完全体"/>
        <Skills>
            <Skill JapaneseName="プリティアタック" ChineseName="可爱一击"/>
            <Skill JapaneseName="可爱一击" ChineseName="ブラックマター"/>
        </Skills>
    </Digimon>
    <Digimon JapaneseName="ムシャモン" ChineseName="武士兽">
        <Level DigimonLevel="成熟期"/>
        <Skills>
            <Skill JapaneseName="斬り捨て御免" ChineseName="格杀勿论"/>
        </Skills>
    </Digimon>
    <Digimon JapaneseName="ズバモン" ChineseName="兹巴兽">
        <Level DigimonLevel="成长期"/>
        <Skills>
        </Skills>
    </Digimon>
    <Digimon JapaneseName="ベツモン" ChineseName="冒充兽">
        <Level DigimonLevel="完全体"/>
        <Skills>
            <Skill JapaneseName="つっこみパンチ" ChineseName="吐槽拳"/>
        </Skills>
    </Digimon>
    <Digimon JapaneseName="マンティコアモン" ChineseName="蝎狮兽">
        <Level DigimonLevel="完全体"/>
        <Skills>
            <Skill JapaneseName="トリニティゴスペル" ChineseName="三位一体福音"/>
            <Skill JapaneseName="三位一体福音" ChineseName="アシッドインジェクション"/>
        </Skills>
    </Digimon>
    <Digimon JapaneseName="ラモールモン" ChineseName="拉莫尔兽">
        <Level DigimonLevel="完全体"/>
        <Skills>
            <Skill JapaneseName="禍災爪" ChineseName="祸灾爪"/>
            <Skill JapaneseName="祸灾爪" ChineseName="叩破伐倒"/>
            <Skill JapaneseName="風牙烈巻迅" ChineseName="风牙烈巻迅"/>
            <Skill JapaneseName="豪怨毀永斬" ChineseName="豪怨毀永斩"/>
        </Skills>
    </Digimon>
    <Digimon JapaneseName="ダルクモン" ChineseName="贞德兽">
        <Level DigimonLevel="成熟期"/>
        <Skills>
        </Skills>
    </Digimon>
    <Digimon JapaneseName="レアレアモン" ChineseName="稀有烂泥兽">
        <Level DigimonLevel="完全体"/>
        <Skills>
            <Skill JapaneseName="ディケイズン" ChineseName="朽烂"/>
            <Skill JapaneseName="朽烂" ChineseName="ダイジェス"/>
        </Skills>
    </Digimon>
    <Digimon JapaneseName="ドウモン" ChineseName="妖道兽">
        <Level DigimonLevel="完全体"/>
        <Skills>
            <Skill JapaneseName="呪禁札" ChineseName="咒禁札"/>
            <Skill JapaneseName="咒禁札" ChineseName="鬼門遁甲"/>
        </Skills>
    </Digimon>
    <Digimon JapaneseName="エスピモン" ChineseName="间谍兽">
        <Level DigimonLevel="成长期"/>
        <Skills>
            <Skill JapaneseName="モットボム" ChineseName="旱獭炸弹"/>
        </Skills>
    </Digimon>
    <Digimon JapaneseName="エアドラモン" ChineseName="飞龙兽">
        <Level DigimonLevel="成熟期"/>
        <Skills>
        </Skills>
    </Digimon>
    <Digimon JapaneseName="リュウダモン" ChineseName="龙蛇兽">
        <Level DigimonLevel="成长期"/>
        <Skills>
        </Skills>
    </Digimon>
    <Digimon JapaneseName="ギュウキモン" ChineseName="牛鬼兽">
        <Level DigimonLevel="完全体"/>
        <Skills>
            <Skill JapaneseName="八束染縛" ChineseName="八束染缚"/>
            <Skill JapaneseName="八束染缚" ChineseName="千砲土蜘蛛"/>
        </Skills>
    </Digimon>
    <Digimon JapaneseName="フレイウィザーモン" ChineseName="焰巫师兽">
        <Level DigimonLevel="装甲体"/>
        <Skills>
        </Skills>
    </Digimon>
    <Digimon JapaneseName="トブキャットモン" ChineseName="飞猫兽">
        <Level DigimonLevel="成熟期"/>
        <Skills>
        </Skills>
    </Digimon>
    <Digimon JapaneseName="オボロモン" ChineseName="胧魂兽">
        <Level DigimonLevel="完全体"/>
        <Skills>
            <Skill JapaneseName="幽玄" ChineseName="幽玄"/>
            <Skill JapaneseName="幽玄" ChineseName="千万ノ太刀"/>
            <Skill JapaneseName="羅焼門" ChineseName="罗烧门"/>
        </Skills>
    </Digimon>
    <Digimon JapaneseName="アンティラモン" ChineseName="玉兔兽">
        <Level DigimonLevel="完全体"/>
        <Skills>
            <Skill JapaneseName="マントラチャント" ChineseName="咒语赞歌"/>
            <Skill JapaneseName="咒语赞歌" ChineseName="メディテーションキュア"/>
        </Skills>
    </Digimon>
    <Digimon JapaneseName="パブリモン" ChineseName="报道兽">
        <Level DigimonLevel="成熟期"/>
        <Skills>
            <Skill JapaneseName="ジュークラック" ChineseName="舞跃裂击"/>
            <Skill JapaneseName="舞跃裂击" ChineseName="デュアルプレッサー"/>
        </Skills>
    </Digimon>
    <Digimon JapaneseName="オウリアモン" ChineseName="夹竹桃兽">
        <Level DigimonLevel="完全体"/>
        <Skills>
            <Skill JapaneseName="リーフレッド" ChineseName="叶刃碎"/>
            <Skill JapaneseName="叶刃碎" ChineseName="ジャミール"/>
        </Skills>
    </Digimon>
    <Digimon JapaneseName="シェイドラモン" ChineseName="阴影龙兽">
        <Level DigimonLevel="装甲体"/>
        <Skills>
            <Skill JapaneseName="フレアバスター" ChineseName="闪光爆破"/>
        </Skills>
    </Digimon>
    <Digimon JapaneseName="ゲレモン" ChineseName="卑劣兽">
        <Level DigimonLevel="成熟期"/>
        <Skills>
            <Skill JapaneseName="ハイパースメル" ChineseName="超恶臭"/>
        </Skills>
    </Digimon>
    <Digimon JapaneseName="ギンリュウモン" ChineseName="银龙兽">
        <Level DigimonLevel="成熟期"/>
        <Skills>
        </Skills>
    </Digimon>
    <Digimon JapaneseName="シャンブルモン" ChineseName="毒蘑菇兽">
        <Level DigimonLevel="成熟期"/>
        <Skills>
            <Skill JapaneseName="スイーポア" ChineseName="甜蜜孢子"/>
            <Skill JapaneseName="甜蜜孢子" ChineseName="シャンピオン・ボム"/>
        </Skills>
    </Digimon>
    <Digimon JapaneseName="ウィッチモン" ChineseName="女巫兽">
        <Level DigimonLevel="成熟期"/>
        <Skills>
            <Skill JapaneseName="バルルーナゲイル" ChineseName="烈风"/>
            <Skill JapaneseName="烈风" ChineseName="アクエリープレッシャー"/>
        </Skills>
    </Digimon>
    <Digimon JapaneseName="プッチーモン" ChineseName="爱精灵兽">
        <Level DigimonLevel="装甲体"/>
        <Skills>
        </Skills>
    </Digimon>
    <Digimon JapaneseName="メイクラックモン" ChineseName="缅破兽">
        <Level DigimonLevel="完全体"/>
        <Skills>
            <Skill JapaneseName="カースドクロー" ChineseName="诅咒之爪"/>
            <Skill JapaneseName="诅咒之爪" ChineseName="フェルトメイド"/>
        </Skills>
    </Digimon>
    <Digimon JapaneseName="ダークナイトモン" ChineseName="黑暗骑士兽">
        <Level DigimonLevel="完全体"/>
        <Skills>
            <Skill JapaneseName="ショルダーブレード" ChineseName="肩刃"/>
            <Skill JapaneseName="肩刃" ChineseName="ツインスピア"/>
            <Skill JapaneseName="アンデッドソルジャー" ChineseName="不死战士"/>
        </Skills>
    </Digimon>
    <Digimon JapaneseName="ガワッパモン" ChineseName="河童兽">
        <Level DigimonLevel="成熟期"/>
        <Skills>
            <Skill JapaneseName="ＤＪシューター" ChineseName="DJ射击"/>
            <Skill JapaneseName="DJ射击" ChineseName="ガワッパンチ"/>
        </Skills>
    </Digimon>
    <Digimon JapaneseName="シャウジンモン" ChineseName="沙悟净兽">
        <Level DigimonLevel="完全体"/>
        <Skills>
            <Skill JapaneseName="月牙斬" ChineseName="月牙斩"/>
            <Skill JapaneseName="月牙斩" ChineseName="降妖杖・渦紋の陣"/>
            <Skill JapaneseName="降妖杖・滝の陣" ChineseName="降妖杖·瀑布之阵"/>
        </Skills>
    </Digimon>
    <Digimon JapaneseName="バアルモン" ChineseName="巴力兽">
        <Level DigimonLevel="完全体"/>
        <Skills>
            <Skill JapaneseName="ギルティッシュ" ChineseName="罪符"/>
            <Skill JapaneseName="罪符" ChineseName="カミウチ"/>
            <Skill JapaneseName="リークインフォメーション" ChineseName="泄密"/>
        </Skills>
    </Digimon>
    <Digimon JapaneseName="フジツモン" ChineseName="藤壶兽">
        <Level DigimonLevel="未知"/>
        <Skills>
        </Skills>
    </Digimon>
    <Digimon JapaneseName="オクタモン" ChineseName="章鱼兽">
        <Level DigimonLevel="成熟期"/>
        <Skills>
        </Skills>
    </Digimon>
    <Digimon JapaneseName="クズハモン" ChineseName="葛叶兽">
        <Level DigimonLevel="究极体"/>
        <Skills>
            <Skill JapaneseName="裏飯綱" ChineseName="里饭纲"/>
            <Skill JapaneseName="里饭纲" ChineseName="胎蔵界曼荼羅"/>
        </Skills>
    </Digimon>
    <Digimon JapaneseName="シリウスモン" ChineseName="天狼星兽">
        <Level DigimonLevel="究极体"/>
        <Skills>
            <Skill JapaneseName="コスモブレード" ChineseName="宇宙之剑"/>
            <Skill JapaneseName="宇宙之剑" ChineseName="フォトンブラスター"/>
            <Skill JapaneseName="ブレイクエーサー" ChineseName="恒星破"/>
            <Skill JapaneseName="プラネイトナックル" ChineseName="星球重拳"/>
        </Skills>
    </Digimon>
    <Digimon JapaneseName="リリスモン" ChineseName="莉莉丝兽">
        <Level DigimonLevel="究极体"/>
        <Skills>
            <Skill JapaneseName="ファントムペイン" ChineseName="幻痛"/>
            <Skill JapaneseName="幻痛" ChineseName="ナザルネイル"/>
        </Skills>
    </Digimon>
    <Digimon JapaneseName="エンシェントスフィンクモン" ChineseName="古代狮身人面兽">
        <Level DigimonLevel="究极体"/>
        <Skills>
            <Skill JapaneseName="ダークブラスト" ChineseName="黑暗冲击波"/>
            <Skill JapaneseName="黑暗冲击波" ChineseName="ネクロエクリプス"/>
        </Skills>
    </Digimon>
    <Digimon JapaneseName="ファラオモン" ChineseName="法老兽">
        <Level DigimonLevel="究极体"/>
        <Skills>
        </Skills>
    </Digimon>
    <Digimon JapaneseName="ディルビットモン" ChineseName="迪卢木多兔兽">
        <Level DigimonLevel="究极体"/>
        <Skills>
            <Skill JapaneseName="トラスゲイン" ChineseName="胜利斩击"/>
            <Skill JapaneseName="胜利斩击" ChineseName="バックストラッシュ"/>
            <Skill JapaneseName="ボルジャーグ" ChineseName="破魔双枪"/>
        </Skills>
    </Digimon>
    <Digimon JapaneseName="ゲコモン" ChineseName="怪蛙兽">
        <Level DigimonLevel="成熟期"/>
        <Skills>
            <Skill JapaneseName="クラッシュシンフォニー" ChineseName="碰撞交响乐"/>
        </Skills>
    </Digimon>
    <Digimon JapaneseName="アンフィモン" ChineseName="海后安菲兽">
        <Level DigimonLevel="究极体"/>
        <Skills>
            <Skill JapaneseName="アンブレディフェンダー" ChineseName="伞盾防御"/>
            <Skill JapaneseName="伞盾防御" ChineseName="アクアザンバー"/>
            <Skill JapaneseName="ライバーンブレイク" ChineseName="雷电重击"/>
            <Skill JapaneseName="クリスタルフリーザー" ChineseName="水晶冻结"/>
        </Skills>
    </Digimon>
    <Digimon JapaneseName="サブマリモン" ChineseName="潜鲨兽">
        <Level DigimonLevel="装甲体"/>
        <Skills>
        </Skills>
    </Digimon>
    <Digimon JapaneseName="クティーラモン" ChineseName="克希拉兽">
        <Level DigimonLevel="究极体"/>
        <Skills>
            <Skill JapaneseName="オーシャンヘル" ChineseName="深海地狱"/>
            <Skill JapaneseName="深海地狱" ChineseName="アクアグラインダー"/>
            <Skill JapaneseName="バッカルラッシュ" ChineseName="三舌鞭打"/>
        </Skills>
    </Digimon>
    <Digimon JapaneseName="ツメモン" ChineseName="妖爪兽">
        <Level DigimonLevel="幼年期Ⅱ"/>
        <Skills>
        </Skills>
    </Digimon>
    <Digimon JapaneseName="ズィードミレニアモン" ChineseName="最终千年兽">
        <Level DigimonLevel="究极体"/>
        <Skills>
            <Skill JapaneseName="タイムデストロイヤー" ChineseName="时空破灭"/>
        </Skills>
    </Digimon>
    <Digimon JapaneseName="ムーンミレニアモン" ChineseName="月之千年兽">
        <Level DigimonLevel="究极体"/>
        <Skills>
        </Skills>
    </Digimon>
    <Digimon JapaneseName="クラヴィスエンジェモン" ChineseName="键天使兽">
        <Level DigimonLevel="究极体"/>
        <Skills>
            <Skill JapaneseName="ザ・キー" ChineseName="关键之钥"/>
        </Skills>
    </Digimon>
    <Digimon JapaneseName="ホバーエスピモン" ChineseName="悬浮间谍兽">
        <Level DigimonLevel="成熟期"/>
        <Skills>
            <Skill JapaneseName="スタンパーミサイル" ChineseName="刻印导弹"/>
            <Skill JapaneseName="刻印导弹" ChineseName="ドロンガー"/>
            <Skill JapaneseName="ダイバニッシュ" ChineseName="隐形谍影"/>
        </Skills>
    </Digimon>
    <Digimon JapaneseName="クオーツモン" ChineseName="晶界兽">
        <Level DigimonLevel="究极体"/>
        <Skills>
            <Skill JapaneseName="ルーインブラスト" ChineseName="破灭炸药"/>
            <Skill JapaneseName="破灭炸药" ChineseName="ギュプト粒子砲"/>
        </Skills>
    </Digimon>
    <Digimon JapaneseName="ダゴモン" ChineseName="达高兽">
        <Level DigimonLevel="完全体"/>
        <Skills>
            <Skill JapaneseName="フォービドゥントライデント" ChineseName="禁忌三叉戟"/>
        </Skills>
    </Digimon>
    <Digimon JapaneseName="コカブテリモン" ChineseName="小比多兽">
        <Level DigimonLevel="成长期"/>
        <Skills>
        </Skills>
    </Digimon>
    <Digimon JapaneseName="ラフレシモン" ChineseName="大王花兽">
        <Level DigimonLevel="究极体"/>
        <Skills>
            <Skill JapaneseName="ウィスレン" ChineseName="改变"/>
            <Skill JapaneseName="改变" ChineseName="バレエガン"/>
        </Skills>
    </Digimon>
    <Digimon JapaneseName="ブルムロードモン" ChineseName="花开领主兽">
        <Level DigimonLevel="究极体"/>
        <Skills>
            <Skill JapaneseName="マルチプルシード" ChineseName="复合之种"/>
            <Skill JapaneseName="复合之种" ChineseName="スプラウトラッシュ"/>
            <Skill JapaneseName="グラン・デル・ソル" ChineseName="烈阳宏光"/>
        </Skills>
    </Digimon>
    <Digimon JapaneseName="レグルスモン" ChineseName="轩辕十四兽">
        <Level DigimonLevel="完全体"/>
        <Skills>
            <Skill JapaneseName="グラントレース" ChineseName="黯星湮灭"/>
            <Skill JapaneseName="黯星湮灭" ChineseName="ゲニアス"/>
        </Skills>
    </Digimon>
    <Digimon JapaneseName="クオンタモン" ChineseName="库恩塔兽">
        <Level DigimonLevel="究极体"/>
        <Skills>
        </Skills>
    </Digimon>
    <Digimon JapaneseName="ディグモン" ChineseName="挖掘兽">
        <Level DigimonLevel="装甲体"/>
        <Skills>
        </Skills>
    </Digimon>
    <Digimon JapaneseName="キロプモン" ChineseName="兜帽蝠兽">
        <Level DigimonLevel="成长期"/>
        <Skills>
            <Skill JapaneseName="パラライズエコー" ChineseName="麻痹声波"/>
            <Skill JapaneseName="麻痹声波" ChineseName="キュリアスアイズ"/>
            <Skill JapaneseName="コンデンスドエコー" ChineseName="压缩音弹"/>
        </Skills>
    </Digimon>
    <Digimon JapaneseName="プリスティモン" ChineseName="小熊猫兽">
        <Level DigimonLevel="成长期"/>
        <Skills>
            <Skill JapaneseName="プリショット" ChineseName="掌心射击"/>
        </Skills>
    </Digimon>
    <Digimon JapaneseName="ウルヴァモン" ChineseName="武装獾兽">
        <Level DigimonLevel="成熟期"/>
        <Skills>
            <Skill JapaneseName="ラピッドバースト" ChineseName="极速爆破"/>
            <Skill JapaneseName="极速爆破" ChineseName="トムボーイブレイズ"/>
            <Skill JapaneseName="スキャッターロケット" ChineseName="散射火箭"/>
            <Skill JapaneseName="バージャースラッシュ" ChineseName="猛獾锐爪"/>
        </Skills>
    </Digimon>
    <Digimon JapaneseName="ゲッコーモン" ChineseName="守宫兽">
        <Level DigimonLevel="成长期"/>
        <Skills>
            <Skill JapaneseName="スマッシュビート" ChineseName="粉碎击"/>
            <Skill JapaneseName="粉碎击" ChineseName="ブレイクスロー"/>
            <Skill JapaneseName="スイングタックル" ChineseName="回旋猛撞"/>
        </Skills>
    </Digimon>
    <Digimon JapaneseName="ハイエモン" ChineseName="鬣狗獸">
        <Level DigimonLevel="成长期"/>
        <Skills>
        </Skills>
    </Digimon>
    <Digimon JapaneseName="ファングモン" ChineseName="獠牙兽">
        <Level DigimonLevel="成熟期"/>
        <Skills>
            <Skill JapaneseName="ブラストコフィン" ChineseName="爆破灵棺"/>
        </Skills>
    </Digimon>
    <Digimon JapaneseName="ケンキモン" ChineseName="建机兽">
        <Level DigimonLevel="装甲体"/>
        <Skills>
        </Skills>
    </Digimon>
    <Digimon JapaneseName="アスタモン" ChineseName="阿斯塔兽">
        <Level DigimonLevel="完全体"/>
        <Skills>
        </Skills>
    </Digimon>
    <Digimon JapaneseName="ブラックガオガモン" ChineseName="黑加奥加兽">
        <Level DigimonLevel="成熟期"/>
        <Skills>
        </Skills>
    </Digimon>
    <Digimon JapaneseName="ムラサメモン" ChineseName="丛雨兽">
        <Level DigimonLevel="完全体"/>
        <Skills>
            <Skill JapaneseName="柔ノ斬・月時雨（じゅうのざん・つきしぐれ）" ChineseName="柔之斩·月时雨"/>
            <Skill JapaneseName="柔之斩·月时雨" ChineseName="豪ノ斬・叢時雨（ごうのざん・むらしぐれ）"/>
            <Skill JapaneseName="終ノ斬・哭雨（ついのざん・こくう）" ChineseName="终之斩·哭雨"/>
        </Skills>
    </Digimon>
    <Digimon JapaneseName="クーガモン" ChineseName="空牙兽">
        <Level DigimonLevel="成熟期"/>
        <Skills>
            <Skill JapaneseName="ラースロア" ChineseName="狂怒咆哮"/>
            <Skill JapaneseName="狂怒咆哮" ChineseName="フリーデスフォール"/>
        </Skills>
    </Digimon>
    <Digimon JapaneseName="ミミックモン" ChineseName="拟态兽">
        <Level DigimonLevel="成熟期"/>
        <Skills>
            <Skill JapaneseName="デッドショット" ChineseName="死亡射击"/>
        </Skills>
    </Digimon>
    <Digimon JapaneseName="シェイドモン" ChineseName="阴影兽">
        <Level DigimonLevel="成熟期"/>
        <Skills>
            <Skill JapaneseName="キルミー" ChineseName="消灭我"/>
        </Skills>
    </Digimon>
    <Digimon JapaneseName="コールドヌメモン" ChineseName="黄金鼻涕兽">
        <Level DigimonLevel="成熟期"/>
        <Skills>
            <Skill JapaneseName="ゴルドリアンラッシュ" ChineseName="黄金榴莲冲刺"/>
            <Skill JapaneseName="黄金榴莲冲刺" ChineseName="ゴールドエクスクレメント"/>
        </Skills>
    </Digimon>
    <Digimon JapaneseName="ナイトキロプモン" ChineseName="夜蝠兽">
        <Level DigimonLevel="成熟期"/>
        <Skills>
            <Skill JapaneseName="プロビデンススキャン" ChineseName="天启扫描"/>
            <Skill JapaneseName="天启扫描" ChineseName="シャドウアーツ"/>
            <Skill JapaneseName="ジャイアントラング" ChineseName="巨型回旋镖"/>
            <Skill JapaneseName="メズマバースト" ChineseName="催眠爆裂"/>
        </Skills>
    </Digimon>
    <Digimon JapaneseName="フレアモン" ChineseName="耀狮兽">
        <Level DigimonLevel="完全体"/>
        <Skills>
            <Skill JapaneseName="紅蓮獣王波" ChineseName="红莲兽王波"/>
        </Skills>
    </Digimon>
    <Digimon JapaneseName="ケコモン" ChineseName="呱呱兽">
        <Level DigimonLevel="幼年期Ⅰ"/>
        <Skills>
        </Skills>
    </Digimon>
    <Digimon JapaneseName="マリンブルモン" ChineseName="海蛞蝓兽">
        <Level DigimonLevel="完全体"/>
        <Skills>
        </Skills>
    </Digimon>
    <Digimon JapaneseName="アルマリザモン" ChineseName="重甲蜥兽">
        <Level DigimonLevel="成熟期"/>
        <Skills>
            <Skill JapaneseName="デスロールプレス" ChineseName="死亡翻滚重压"/>
            <Skill JapaneseName="死亡翻滚重压" ChineseName="ニュートロンレイザー"/>
            <Skill JapaneseName="ニュートロンブレイド" ChineseName="中子利刃"/>
            <Skill JapaneseName="ニュートロンデフューザー" ChineseName="中子扩散"/>
        </Skills>
    </Digimon>
    <Digimon JapaneseName="ゴクウモン" ChineseName="悟空兽">
        <Level DigimonLevel="完全体"/>
        <Skills>
        </Skills>
    </Digimon>
    <Digimon JapaneseName="ボンバーナニモン" ChineseName="炸弹什么兽">
        <Level DigimonLevel="成熟期"/>
        <Skills>
            <Skill JapaneseName="フリースローボム" ChineseName="罚球炸弹"/>
        </Skills>
    </Digimon>
    <Digimon JapaneseName="モノドラモン" ChineseName="单角龙兽">
        <Level DigimonLevel="成长期"/>
        <Skills>
            <Skill JapaneseName="ビートナックル" ChineseName="冲击拳头"/>
        </Skills>
    </Digimon>
    <Digimon JapaneseName="シャコモン" ChineseName="虾蛄兽">
        <Level DigimonLevel="成长期"/>
        <Skills>
            <Skill JapaneseName="ウォータースクリュー" ChineseName="水螺旋"/>
        </Skills>
    </Digimon>
    <Digimon JapaneseName="ランフォモン" ChineseName="喙嘴龙兽">
        <Level DigimonLevel="成熟期"/>
        <Skills>
            <Skill JapaneseName="クリスタルキャノン" ChineseName="水晶加农"/>
            <Skill JapaneseName="水晶加农" ChineseName="ハンマーストライク"/>
            <Skill JapaneseName="クリスタルレイン" ChineseName="水晶之雨"/>
        </Skills>
    </Digimon>
    <Digimon JapaneseName="ルドモン" ChineseName="路德兽">
        <Level DigimonLevel="成长期"/>
        <Skills>
        </Skills>
    </Digimon>
    <Digimon JapaneseName="ティロモン" ChineseName="海王龙兽">
        <Level DigimonLevel="装甲体"/>
        <Skills>
            <Skill JapaneseName="オーシャンストライク" ChineseName="海流突袭"/>
            <Skill JapaneseName="海流突袭" ChineseName="トーピードアタック"/>
        </Skills>
    </Digimon>
    <Digimon JapaneseName="ムースモン" ChineseName="驼鹿兽">
        <Level DigimonLevel="装甲体"/>
        <Skills>
        </Skills>
    </Digimon>
    <Digimon JapaneseName="ばぷモン/ば～ぷモン" ChineseName="饱嗝兽">
        <Level DigimonLevel="未知"/>
        <Skills>
        </Skills>
    </Digimon>
    <Digimon JapaneseName="コマンドラモン" ChineseName="突击龙兽">
        <Level DigimonLevel="成长期"/>
        <Skills>
        </Skills>
    </Digimon>
    <Digimon JapaneseName="ボムモン" ChineseName="炸弹兽">
        <Level DigimonLevel="幼年期Ⅰ"/>
        <Skills>
        </Skills>
    </Digimon>
    <Digimon JapaneseName="ティンカーモン" ChineseName="汀克兽">
        <Level DigimonLevel="成长期"/>
        <Skills>
            <Skill JapaneseName="スピードナイトメア" ChineseName="速入恶梦"/>
        </Skills>
    </Digimon>
    <Digimon JapaneseName="アズダルモン" ChineseName="神龙翼兽">
        <Level DigimonLevel="完全体"/>
        <Skills>
            <Skill JapaneseName="トマホークストライク" ChineseName="战斧突击"/>
            <Skill JapaneseName="战斧突击" ChineseName="トリニティライトニング"/>
            <Skill JapaneseName="トライカーヴレイン" ChineseName="三重斩击雨"/>
        </Skills>
    </Digimon>
    <Digimon JapaneseName="ケッコモン" ChineseName="可口兽">
        <Level DigimonLevel="幼年期Ⅱ"/>
        <Skills>
        </Skills>
    </Digimon>
    <Digimon JapaneseName="マリンキメラモン" ChineseName="海奇美拉兽">
        <Level DigimonLevel="完全体"/>
        <Skills>
            <Skill JapaneseName="アクアバイパー" ChineseName="水流毒蛇"/>
        </Skills>
    </Digimon>
    <Digimon JapaneseName="ライラモン" ChineseName="丁香兽">
        <Level DigimonLevel="完全体"/>
        <Skills>
        </Skills>
    </Digimon>
    <Digimon JapaneseName="プロガノモン" ChineseName="原颚甲兽">
        <Level DigimonLevel="完全体"/>
        <Skills>
            <Skill JapaneseName="ドリルエミッション" ChineseName="喷射钻头"/>
        </Skills>
    </Digimon>
    <Digimon JapaneseName="ププモン" ChineseName="普普兽">
        <Level DigimonLevel="幼年期Ⅰ"/>
        <Skills>
        </Skills>
    </Digimon>
    <Digimon JapaneseName="モクモン" ChineseName="烟尘兽">
        <Level DigimonLevel="幼年期Ⅰ"/>
        <Skills>
        </Skills>
    </Digimon>
    <Digimon JapaneseName="プスモン" ChineseName="刺刺兽">
        <Level DigimonLevel="幼年期Ⅰ"/>
        <Skills>
        </Skills>
    </Digimon>
    <Digimon JapaneseName="クリモン" ChineseName="溜溜兽">
        <Level DigimonLevel="幼年期Ⅰ"/>
        <Skills>
        </Skills>
    </Digimon>
    <Digimon JapaneseName="プチモン" ChineseName="小龙兽">
        <Level DigimonLevel="幼年期Ⅰ"/>
        <Skills>
        </Skills>
    </Digimon>
    <Digimon JapaneseName="サクモン" ChineseName="萨库兽">
        <Level DigimonLevel="幼年期Ⅰ"/>
        <Skills>
        </Skills>
    </Digimon>
    <Digimon JapaneseName="キーモン" ChineseName="嘿嘿兽">
        <Level DigimonLevel="幼年期Ⅰ"/>
        <Skills>
        </Skills>
    </Digimon>
    <Digimon JapaneseName="ココモン" ChineseName="可可兽">
        <Level DigimonLevel="幼年期Ⅰ"/>
        <Skills>
        </Skills>
    </Digimon>
    <Digimon JapaneseName="パフモン" ChineseName="膨膨兽">
        <Level DigimonLevel="幼年期Ⅰ"/>
        <Skills>
        </Skills>
    </Digimon>
    <Digimon JapaneseName="フフモン" ChineseName="步步兽">
        <Level DigimonLevel="幼年期Ⅰ"/>
        <Skills>
        </Skills>
    </Digimon>
    <Digimon JapaneseName="クラモン" ChineseName="水母兽">
        <Level DigimonLevel="幼年期Ⅰ"/>
        <Skills>
        </Skills>
    </Digimon>
    <Digimon JapaneseName="ゴールドヌメモン" ChineseName="黄金鼻涕兽">
        <Level DigimonLevel="成熟期"/>
        <Skills>
        </Skills>
    </Digimon>
    <Digimon JapaneseName="グラビモン" ChineseName="重力兽">
        <Level DigimonLevel="完全体"/>
        <Skills>
        </Skills>
    </Digimon>
    <Digimon JapaneseName="アカトリモン" ChineseName="红鸡兽">
        <Level DigimonLevel="成熟期"/>
        <Skills>
        </Skills>
    </Digimon>
    <Digimon JapaneseName="インプモン" ChineseName="小妖兽">
        <Level DigimonLevel="成长期"/>
        <Skills>
        </Skills>
    </Digimon>
    <Digimon JapaneseName="ツカイモン" ChineseName="使魔兽">
        <Level DigimonLevel="成长期"/>
        <Skills>
        </Skills>
    </Digimon>
    <Digimon JapaneseName="シーサモン" ChineseName="风狮兽">
        <Level DigimonLevel="成熟期"/>
        <Skills>
        </Skills>
    </Digimon>
    <Digimon JapaneseName="ケトモン" ChineseName="踢踢兽">
        <Level DigimonLevel="幼年期Ⅰ"/>
        <Skills>
        </Skills>
    </Digimon>
    <Digimon JapaneseName="ティアルドモン" ChineseName="提亚路德兽">
        <Level DigimonLevel="成熟期"/>
        <Skills>
        </Skills>
    </Digimon>
    <Digimon JapaneseName="ピラミディモン" ChineseName="金字塔兽">
        <Level DigimonLevel="究极体"/>
        <Skills>
            <Skill JapaneseName="ラアナハムシーン" ChineseName="诅咒沙暴"/>
            <Skill JapaneseName="诅咒沙暴" ChineseName="アペシュイカーブ"/>
            <Skill JapaneseName="ゾフルカーブース" ChineseName="沙爪噩梦"/>
        </Skills>
    </Digimon>
    <Digimon JapaneseName="モナークリザモン" ChineseName="王者蜥兽">
        <Level DigimonLevel="完全体"/>
        <Skills>
            <Skill JapaneseName="アナイアレイトエッジ" ChineseName="毁灭巨刃"/>
            <Skill JapaneseName="毁灭巨刃" ChineseName="ファイナルジャッジメント"/>
        </Skills>
    </Digimon>
    <Digimon JapaneseName="スターモン" ChineseName="星星兽">
        <Level DigimonLevel="成熟期"/>
        <Skills>
            <Skill JapaneseName="メテオスコール" ChineseName="流星暴雨"/>
        </Skills>
    </Digimon>
    <Digimon JapaneseName="エリザモン" ChineseName="皇后襟蜥兽">
        <Level DigimonLevel="成长期"/>
        <Skills>
            <Skill JapaneseName="フリルドカッター" ChineseName="褶饰切割"/>
            <Skill JapaneseName="褶饰切割" ChineseName="ヘリコプテイル"/>
        </Skills>
    </Digimon>
    <Digimon JapaneseName="" ChineseName="">
        <Level DigimonLevel=""/>
        <Skills>
        </Skills>
    </Digimon>
    <Digimon JapaneseName="" ChineseName="">
        <Level DigimonLevel=""/>
        <Skills>
        </Skills>
    </Digimon>
    <Digimon JapaneseName="" ChineseName="">
        <Level DigimonLevel=""/>
        <Skills>
        </Skills>
    </Digimon>
    <Digimon JapaneseName="" ChineseName="">
        <Level DigimonLevel=""/>
        <Skills>
        </Skills>
    </Digimon>
    <Digimon JapaneseName="" ChineseName="">
        <Level DigimonLevel=""/>
        <Skills>
        </Skills>
    </Digimon>
    <Digimon JapaneseName="" ChineseName="">
        <Level DigimonLevel=""/>
        <Skills>
        </Skills>
    </Digimon>
    <!--Split-->
    <HumanCharacter JapaneseName="八神太一" ChineseName="八神太一"/>
    <HumanCharacter JapaneseName="西島大吾" ChineseName="西岛大吾"/>
    <HumanCharacter JapaneseName="ゲンナイ" ChineseName="玄内"/>
    <HumanCharacter JapaneseName="石田ヤマト" ChineseName="石田大和"/>
    <HumanCharacter JapaneseName="姬川マキ" ChineseName="姬川真希"/>
    <HumanCharacter JapaneseName="ホメオスタシス" ChineseName="恒常性"/>
    <HumanCharacter JapaneseName="武之内空" ChineseName="武之内空"/>
    <HumanCharacter JapaneseName="八神裕子" ChineseName="八神裕子"/>
    <HumanCharacter JapaneseName="泉光子郎" ChineseName="泉光子郎"/>
    <HumanCharacter JapaneseName="泉政実" ChineseName="泉政实"/>
    <HumanCharacter JapaneseName="太刀川ミミ" ChineseName="太刀川美美"/>
    <HumanCharacter JapaneseName="泉佳江" ChineseName="泉佳江"/>
    <HumanCharacter JapaneseName="城戸丈" ChineseName="城户丈"/>
    <HumanCharacter JapaneseName="メノア・ベルッチ" ChineseName="梅诺阿·贝鲁奇"/>
    <HumanCharacter JapaneseName="高石タケル" ChineseName="高石岳"/>
    <HumanCharacter JapaneseName="井村京太郎" ChineseName="井村京太郎"/>
    <HumanCharacter JapaneseName="八神ヒカリ" ChineseName="八神光"/>
    <HumanCharacter JapaneseName="城戶進" ChineseName="城户进"/>
    <HumanCharacter JapaneseName="本宮大輔" ChineseName="本宫大辅"/>
    <HumanCharacter JapaneseName="城戶修" ChineseName="城户修"/>
    <HumanCharacter JapaneseName="一乗寺賢" ChineseName="一乘寺贤"/>
    <HumanCharacter JapaneseName="神原由利子" ChineseName="神原由利子"/>
    <HumanCharacter JapaneseName="火田伊織" ChineseName="火田伊织"/>
    <HumanCharacter JapaneseName="神原信也" ChineseName="神原信也"/>
    <HumanCharacter JapaneseName="井ノ上 京" ChineseName="井上京"/>
    <HumanCharacter JapaneseName="神原宏明" ChineseName="神原宏明"/>
    <HumanCharacter JapaneseName="望月芽心" ChineseName="望月芽心"/>
    <HumanCharacter JapaneseName="篠宮ヒトミ" ChineseName="筱宫仁美"/>
    <HumanCharacter JapaneseName="神原拓也" ChineseName="神原拓也"/>
    <HumanCharacter JapaneseName="天馬アスカ" ChineseName="天马飞鸟"/>
    <HumanCharacter JapaneseName="源輝二" ChineseName="源辉二"/>
    <HumanCharacter JapaneseName="辔田マキ" ChineseName="辔田真希"/>
    <HumanCharacter JapaneseName="氷見友樹" ChineseName="冰见友树"/>
    <HumanCharacter JapaneseName="河原崎" ChineseName="河原崎"/>
    <HumanCharacter JapaneseName="織本泉" ChineseName="织本泉"/>
    <HumanCharacter JapaneseName="ヨッシー" ChineseName="小吉"/>
    <HumanCharacter JapaneseName="柴山純平" ChineseName="柴山纯平"/>
    <HumanCharacter JapaneseName="吉村" ChineseName="吉村"/>
    <HumanCharacter JapaneseName="木村輝一" ChineseName="木村辉一"/>
    <HumanCharacter JapaneseName="遊狩" ChineseName="游狩"/>
    <HumanCharacter JapaneseName="天ノ河宙" ChineseName="天之河宙"/>
    <HumanCharacter JapaneseName="山田ハルコ" ChineseName="山田春子"/>
    <HumanCharacter JapaneseName="月夜野瑠璃" ChineseName="月夜野瑠璃"/>
    <HumanCharacter JapaneseName="天ノ河北斗" ChineseName="天之河北斗"/>
    <HumanCharacter JapaneseName="りるるん" ChineseName="璃瑠瑠"/>
    <HumanCharacter JapaneseName="野村コタロウ" ChineseName="野村虎太郎"/>
    <HumanCharacter JapaneseName="東御手洗清司郎" ChineseName="东御手洗清司郎"/>
    <HumanCharacter JapaneseName="柏木ミカ" ChineseName="柏木美佳"/>
    <HumanCharacter JapaneseName="天馬トモロウ" ChineseName="天马智郎"/>
    <HumanCharacter JapaneseName="宇田川アオイ" ChineseName="宇田川葵"/>
    <HumanCharacter JapaneseName="咲夜レーナ" ChineseName="咲夜玲奈"/>
    <HumanCharacter JapaneseName="深津理久" ChineseName="深津理久"/>
    <HumanCharacter JapaneseName="久遠寺マコト" ChineseName="久远寺诚"/>
    <HumanCharacter JapaneseName="忽那カイト" ChineseName="忽那海斗"/>
    <HumanCharacter JapaneseName="沢城キョウ" ChineseName="泽城京"/>
    <HumanCharacter JapaneseName="金田ゲンジョウ" ChineseName="金田源城"/>
    <HumanCharacter JapaneseName="沙海ホノカ" ChineseName="沙海帆霞"/>
    <HumanCharacter JapaneseName="ローズ・ウッドヴィル" ChineseName="罗丝・伍德薇尔"/>
    <HumanCharacter JapaneseName="クレイ・アルスラン" ChineseName="科雷・亚禄斯兰"/>
    <HumanCharacter JapaneseName="王会長" ChineseName="王会长"/>
    <HumanCharacter JapaneseName="セラフィ　内藤" ChineseName="塞拉菲・内藤"/>
    <HumanCharacter JapaneseName="ルカ・グラニット" ChineseName="卢卡・格拉尼特"/>
    <HumanCharacter JapaneseName="鹿沼ホタルコ" ChineseName="鹿沼萤子"/>
    <HumanCharacter JapaneseName="惣田ライト" ChineseName="惣田赖人"/>
    <HumanCharacter JapaneseName="ステラ" ChineseName="史黛拉"/>
    <HumanCharacter JapaneseName="鹿沼コウ" ChineseName="鹿沼红"/>
    <HumanCharacter JapaneseName="鹿沼アオ" ChineseName="鹿沼青"/>
    <HumanCharacter JapaneseName="曽根ハルオミ" ChineseName="曾根晴臣"/>
    <HumanCharacter JapaneseName="幾原ユメ" ChineseName="几原梦"/>
    <!--Split-->
    <Location Category="现实世界地名">
        <Entry JapaneseName="光が丘" ChineseName="光丘"/>
    </Location>
    <Location Category="数码世界地名">
        <Entry JapaneseName="デジタルワールド" ChineseName="数码世界"/>
    </Location>
    <Others>
        <Entry JapaneseName="デジヴァイス" ChineseName="数码器"/>
    </Others>
    <Idioms description="固定翻译">
        <Entry JapaneseSentence="今 冒険が進化する" ChineseSentence="现在 冒险在不断进化" Comment=""/>
    </Idioms>
    <Location Category="现实世界地名">
        <Entry JapaneseName="お台場" ChineseName="御台场"/>
    </Location>
    <Location Category="数码世界地名">
        <Entry JapaneseName="ファイル島" ChineseName="法易路岛/文件岛"/>
    </Location>
    <Others>
        <Entry JapaneseName="D-3" ChineseName="D-3"/>
    </Others>
    <Idioms description="固定翻译">
        <Entry JapaneseSentence="今 再び 冒険が進化する" ChineseSentence="现在 冒险再一次进化" Comment=""/>
    </Idioms>
    <Location Category="现实世界地名">
        <Entry JapaneseName="関東地方" ChineseName="关东地区"/>
    </Location>
    <Location Category="数码世界地名">
        <Entry JapaneseName="竜の目の湖" ChineseName="龙眼湖"/>
    </Location>
    <Others>
        <Entry JapaneseName="紋章" ChineseName="徽章"/>
    </Others>
    <Idioms description="固定翻译">
        <Entry JapaneseSentence="冒険は 新たな世界へ" ChineseSentence="冒险 向着全新世界进发" Comment=""/>
    </Idioms>
    <Location Category="现实世界地名">
        <Entry JapaneseName="鳥取" ChineseName="鸟取"/>
    </Location>
    <Location Category="数码世界地名">
        <Entry JapaneseName="じまりの街" ChineseName="创始村"/>
    </Location>
    <Others>
        <Entry JapaneseName="黒い歯車" ChineseName="黑色齿轮"/>
    </Others>
    <Idioms description="固定翻译">
        <Entry JapaneseSentence="さて　僕のチェックポイント" ChineseSentence="接下来我要说的是重点" Comment=""/>
    </Idioms>
    <Location Category="现实世界地名">
        <Entry JapaneseName="東京湾" ChineseName="东京湾"/>
    </Location>
    <Location Category="数码世界地名">
        <Entry JapaneseName="サーバー大陸" ChineseName="沙拔大陆/服务器大陆"/>
    </Location>
    <Others>
        <Entry JapaneseName="黒いケーブル" ChineseName="黑色电缆"/>
    </Others>
    <Idioms description="固定翻译">
        <Entry JapaneseSentence="次回はどんなデジモンかな" ChineseSentence="下一次是哪只数码兽呢" Comment=""/>
    </Idioms>
    <Location Category="现实世界地名">
        <Entry JapaneseName="東京タワー" ChineseName="东京塔"/>
    </Location>
    <Location Category="数码世界地名">
        <Entry JapaneseName="無限マウンテン" ChineseName="无限山"/>
    </Location>
    <Others>
        <Entry JapaneseName="デジモンカード" ChineseName="数码兽卡"/>
    </Others>
    <Idioms description="固定翻译">
        <Entry JapaneseSentence="気張るわよ" ChineseSentence="一鼓作气(哦|上吧)" Comment="咲夜玲奈专用"/>
    </Idioms>
    <Location Category="现实世界地名">
        <Entry JapaneseName="東京ビッグサイト" ChineseName="东京国际展示场"/>
    </Location>
    <Location Category="数码世界地名">
        <Entry JapaneseName="ミハラシ山" ChineseName="米哈拉西山"/>
    </Location>
    <Others>
        <Entry JapaneseName="選ばれし子供" ChineseName="被选召的孩子"/>
    </Others>
    <Idioms description="固定翻译">
        <Entry JapaneseSentence="打ち鳴らせ" ChineseSentence="响彻吧" Comment="天马智郎专用"/>
    </Idioms>
    <Location Category="现实世界地名">
        <Entry JapaneseName="FCGビル" ChineseName="富士产经集团大楼"/>
    </Location>
    <Location Category="数码世界地名">
        <Entry JapaneseName="オーバーデル墓地" ChineseName="欧帕迪墓地"/>
    </Location>
    <Others>
        <Entry JapaneseName="タグ" ChineseName="进化钥匙"/>
    </Others>
    <Idioms description="固定翻译">
        <Entry JapaneseSentence="羽ばたけ" ChineseSentence="展翅飞翔吧" Comment="久远寺诚专用"/>
    </Idioms>
    <Location Category="现实世界地名">
        <Entry JapaneseName="お台場小学校" ChineseName="御台场小学"/>
    </Location>
    <Location Category="数码世界地名">
        <Entry JapaneseName="メンタル" ChineseName="云端大陆"/>
    </Location>
    <Others>
        <Entry JapaneseName="デジコード" ChineseName="数码密码"/>
    </Others>
    <Idioms description="固定翻译">
        <Entry JapaneseSentence="狩り尽くしなさい" ChineseSentence="狩猎干净吧" Comment="鹿沼萤子专用"/>
    </Idioms>
    <Location Category="现实世界地名">
        <Entry JapaneseName="パレットタウン" ChineseName="调色板城"/>
    </Location>
    <Location Category="数码世界地名">
        <Entry JapaneseName="炎のターミナル" ChineseName="火焰终点站"/>
    </Location>
    <Others>
        <Entry JapaneseName="スピリット" ChineseName="斗士之魂"/>
    </Others>
    <Location Category="现实世界地名">
        <Entry JapaneseName="羽田空港" ChineseName="羽田机场"/>
    </Location>
    <Location Category="数码世界地名">
        <Entry JapaneseName="ダークエリア" ChineseName="黑暗区域タクティクス"/>
    </Location>
    <Others>
        <Entry JapaneseName="スピリット　エヴォリューション" ChineseName="斗士之魂 进化"/>
    </Others>
    <Location Category="现实世界地名">
        <Entry JapaneseName="月島総合高校" ChineseName="月岛综合高中"/>
    </Location>
    <Location Category="数码世界地名">
        <Entry JapaneseName="森のターミナル" ChineseName="森林终点站"/>
    </Location>
    <Others>
        <Entry JapaneseName="デジモンカイザー" ChineseName="数码兽皇帝"/>
    </Others>
    <Location Category="现实世界地名">
        <Entry JapaneseName="お台場中学校" ChineseName="御台场中学"/>
    </Location>
    <Location Category="数码世界地名">
        <Entry JapaneseName="コンパイラ大森林" ChineseName="编译器大森林"/>
    </Location>
    <Others>
        <Entry JapaneseName="デジメンタルアップ" ChineseName="数码精神升级"/>
    </Others>
    <Location Category="现实世界地名">
        <Entry JapaneseName="大江戸温泉物語" ChineseName="大江户温泉物语"/>
    </Location>
    <Others>
        <Entry JapaneseName="ｅ－パルス" ChineseName="e脉冲"/>
    </Others>
    <Location Category="现实世界地名">
        <Entry JapaneseName="東京臨海新交通臨海線" ChineseName="东京临海新交通临海线"/>
    </Location>
    <Others>
        <Entry JapaneseName="サポタマ" ChineseName="辅助蛋"/>
    </Others>
    <Location Category="现实世界地名">
        <Entry JapaneseName="レインボーブリッジ" ChineseName="彩虹大桥"/>
    </Location>
    <Others>
        <Entry JapaneseName="コールドハート" ChineseName="心冻症"/>
    </Others>
    <Location Category="现实世界地名">
        <Entry JapaneseName="お台場海浜公園" ChineseName="御台场海滨公园"/>
    </Location>
    <Others>
        <Entry JapaneseName="サポ主" ChineseName="辅助伙伴"/>
    </Others>
    <Location Category="现实世界地名">
        <Entry JapaneseName="渋谷" ChineseName="涩谷"/>
    </Location>
    <Others>
        <Entry JapaneseName="クリーナー" ChineseName="清道夫"/>
    </Others>
    <Location Category="现实世界地名">
        <Entry JapaneseName="葉櫻学院" ChineseName="叶樱学院"/>
    </Location>
    <Others>
        <Entry JapaneseName="グローイングドーン" ChineseName="曙光黎明"/>
    </Others>
    <Location Category="现实世界地名">
        <Entry JapaneseName="シャングリラエッグ" ChineseName="桃源巨蛋"/>
    </Location>
    <Others>
        <Entry JapaneseName="五行星" ChineseName="五行星"/>
    </Others>
    <Location Category="现实世界地名">
        <Entry JapaneseName="サポートセンター" ChineseName="辅助蛋中心"/>
    </Location>
    <Others>
        <Entry JapaneseName="ワールドユニオン" ChineseName="世界联盟"/>
    </Others>
    <Location Category="现实世界地名">
        <Entry JapaneseName="光ヶ浜" ChineseName="光滨"/>
    </Location>
    <Others>
        <Entry JapaneseName="シャングリラ計画" ChineseName="桃源计划"/>
    </Others>
    <Location Category="现实世界地名">
        <Entry JapaneseName="新光ヶ浜高校" ChineseName="新光滨高中"/>
    </Location>
    <Others>
        <Entry JapaneseName="キノコ団" ChineseName="蘑菇团"/>
    </Others>
    <Location Category="现实世界地名">
        <Entry JapaneseName="伽藍堂" ChineseName="伽蓝堂"/>
    </Location>
    <Others>
        <Entry JapaneseName="チームセブン" ChineseName="第七小队"/>
    </Others>
    <Location Category="现实世界地名">
        <Entry JapaneseName="ミラーワールド" ChineseName="镜世界"/>
    </Location>
    <Others>
        <Entry JapaneseName="タクティクス" ChineseName="战术部队"/>
    </Others>
    <Location Category="现实世界地名">
        <Entry JapaneseName="シェルターニリンソウ" ChineseName="鹅掌草避难所"/>
    </Location>
    <Others>
        <Entry JapaneseName="ニリンソウ" ChineseName="鹅掌草防卫队"/>
    </Others>
    <Location Category="现实世界地名">
        <Entry JapaneseName="ハイエンドブロック" ChineseName="高端区"/>
    </Location>
    <Others>
        <Entry JapaneseName="クレジット" ChineseName="信用点"/>
    </Others>
    <Location Category="现实世界地名">
        <Entry JapaneseName="ワールドユニオン総合病院" ChineseName="世界联盟综合医院"/>
    </Location>
    <Others>
        <Entry JapaneseName="国民保護省" ChineseName="国民保护省"/>
    </Others>
    <Location Category="现实世界地名">
        <Entry JapaneseName="アブラクサス" ChineseName="阿卜拉克萨斯"/>
    </Location>
    <Others>
        <Entry JapaneseName="孤荒会" ChineseName="孤荒会"/>
    </Others>
    <Location Category="现实世界地名">
        <Entry JapaneseName="虹島ショッピングモール" ChineseName="虹岛购物中心"/>
    </Location>
    <Location Category="现实世界地名">
        <Entry JapaneseName="アルビダ共和国" ChineseName="亚比达共和国"/>
    </Location>
    <Location Category="现实世界地名">
        <Entry JapaneseName="神生島" ChineseName="神生岛"/>
    </Location>
    <!--Split-->
    <Title JapaneseName="デジモン" ChineseName="数码兽"/>
    <Title JapaneseName="デジタルモンスター" ChineseName="数码怪兽"/>
    <Title JapaneseName="デジモンアドベンチャー" ChineseName="数码兽大冒险"/>
    <Title JapaneseName="デジモンテイマーズ" ChineseName="数码兽驯兽师"/>
    <Title JapaneseName="LAST EVOLUTION 絆" ChineseName="最后的进化 纽带"/>
    <Title JapaneseName="THE BEGINNING" ChineseName="最初的召唤"/>
    <Title JapaneseName="デジモンフロンティア" ChineseName="数码兽最前线"/>
    <Title JapaneseName="デジモンユニバース アプリモンスターズ" ChineseName="数码兽宇宙 应用怪兽"/>
    <Title JapaneseName="デジモンゴーストゲーム" ChineseName="数码兽幽灵游戏"/>
    <Title JapaneseName="デジモンビートブレイク" ChineseName="数码兽觉醒节拍"/>
</Glossary>


<OutputFormat>
    - 仅输出有错误的台词，完全没问题的台词直接跳过。
    - 必须先输出【起始时间】。
    - 错误描述：必须精炼地引用出现问题的原文或译文字段，说明具体错误，并给出修改建议。
    - 格式要求（核心原则）：针对单对台词的检查结果，必须严格合并在同一行内输出，绝对禁止换行！
    - 语言风格：一针见血，无需长篇大论。

    输出示例：
    [00:01:23.45] 标点违规 - 译文“你好。”中包含违规句号和双引号，建议删除句号并改为「你好」。
    [00:02:15.10] 日式汉语 - 译文将「明日のこと」直译为“明天的事”，建议调整语序，删去“的事”。
    [00:03:05.00] 代词错误 - 原文指向数码兽，译文“他怎么了”误用“他”，建议改为“它”。
    [00:04:12.30] 逻辑/错译 - 原文「ああして、こうして」包含多个「して」，译文“这样，那样”未处理逻辑衔接，日式中文严重，建议重组句式。
    [00:05:01.12] 遗留标记 - 译文“快跑*”句末遗留多余 * 号，建议删除。
</OutputFormat>
"""


"""
temperature=0.7, top_p=0.8, top_k=20, min_p=0.0, presence_penalty=1.5, repetition_penalty=1.0
"""

client = ChatOpenAI(base_url=API_HOST,
                    api_key=API_KEY,
                    model=MODEL,
                    # temperature=0.7,
                    # top_p=0.8,
                    # presence_penalty=1.5,
                    # max_tokens=8192,
                    # extra_body={
                    #     "top_k": 20,
                    #     "repetition_penalty": 1.0,
                    #     "min_p": 0.0,
                    #     "chat_template_kwargs": {"enable_thinking": False}
                    # }
                    )

def read_all_lines(file:Path):
    with file.open("r",encoding="utf-8") as ins:
        lines=list(ins.readlines())
        return lines


def read_ass_as_xml(file:Path):
    subs = pysubs2.load(str(file))
    for line in subs:
        if line.is_comment or line.style!="Default":
            continue

        start_time=pysubs2.time.ms_to_str(line.start,fractions=True)
        text=line.text
        if len(text.strip())==0:
            continue
        chinese,japanese=text.split(r"\N{\fnG-OTF Jo Shin Maru Go ProN M\fs45}")
        yield f"<TranslationLine><StartTime>{start_time}</StartTime><ChineseText>{chinese.strip()}</ChineseText><JapaneseText>{japanese.strip()}</<JapaneseText></TranslationLine>"

def main():
    parser = argparse.ArgumentParser(description="中日字幕校对工具")
    parser.add_argument("-f", "--file", type=Path, required=True, help="输入的 .ass 字幕文件路径")
    parser.add_argument("-o", "--output", type=Path, default=None, help="输出结果文件路径（默认为 result-<timestamp>.txt）")
    args = parser.parse_args()

    assfile = args.file
    output = args.output or Path(f"result-{timestamp}.txt")

    lines=list(read_ass_as_xml(assfile))
    total_response=[]
    strParser = StrOutputParser()
    for i in range(0, len(lines), 30):
        chunk = lines[i: i + 30]
        human = HumanMessage(
            "<Task>请校对以下字幕<Task>\n<Subtitle>\n{}\n</Subtitle>".format("\n".join(chunk))
        )
        msgs = [SystemMessage(SYSTEM_PROMPT),human]
        result=client.invoke(msgs)
        response=strParser.invoke(result)
        print(response)
        total_response.append(response)
    with output.open("w",encoding="utf-8") as ofs:
        ofs.write("\n".join(total_response))


if __name__ == "__main__":
    main()
