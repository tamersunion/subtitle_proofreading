#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import openpyxl

"""
Instruction：

现在需要你写一个程序将一个xlsx（glossary.xlsx）转换为xml

需求如下

1. 整个XML由<Glossary></Glossary>包裹
2. xlsx有4个sheet，他们分别为“数码兽及其技能名”、“人类及其他非数码兽角色名”、“地名、道具名及其他专有名词”、“作品名”
3. 第一行为均表头
4. 对于“数码兽及其技能名”每一行进行如下处理，各行处理后的xml以换行隔开
    <Digimon JapaneseName="${第A列}" ChineseName="${第B列}">
        <Level DigimonLevel="${第C列}">
        <Skills>
            <Skill JapaneseName="${第D列}" ChineseName="${第E列}"/>
            <Skill JapaneseName="${第F列}" ChineseName="${第G列}"/>
            <Skill JapaneseName="${第H列}" ChineseName="${第I列}"/>
            <Skill JapaneseName="${第J列}" ChineseName="${第K列}"/>
            <Skill JapaneseName="${第L列}" ChineseName="${第L列}"/>
        </Skills>
    </Digimon>
    注意：所有skills里面，如果JapaneseName和ChineseName任意一个为空（判断条件为 len(s.strip())==0），那么就不记录这一个skill的节点
5. 对于“人类及其他非数码兽角色名”的每一行进行如下处理，各行处理后的xml以换行隔开
    <HumanCharacter JapaneseName="${第A列}" ChineseName="${第B列}"/>
    <HumanCharacter JapaneseName="${第C列}" ChineseName="${第D列}"/>
    <HumanCharacter JapaneseName="${第E列}" ChineseName="${第F列}"/>
    注意：所有HumanCharacter里面，如果JapaneseName和ChineseName任意一个为空（判断条件为 len(s.strip())==0），那么就不记录这一个HumanCharacter的节点
6. 对于“地名、道具名及其他专有名词”的每一行进行如下处理，各行处理后的xml以换行隔开
    <Location Category="现实世界地名">
        <Entry JapaneseName="${第A列}" ChineseName="${第B列}"/>
    </Location>
    <Location Category="数码世界地名">
        <Entry JapaneseName="${第C列}" ChineseName="${第D列}"/>
    </Location>
    <Others>
        <Entry JapaneseName="${第E列}" ChineseName="${第F列}"/>
    </Others>
    <Idioms description="固定翻译">
        <Entry JapaneseSentence="${第G列}" ChineseSentence="${第H列}" Comment="${第I列}">
    </Idioms>
7. 对于“作品名”的每一行进行处理，各行处理后的xml以换行隔开
    <Title JapaneseName="${第A列}" ChineseName="${第B列}"/>
8. 4~7的内容以换行和<!--Split-->隔开
9. 保存到glossary.xml里面

"""

def safe_str(val):
    if val is None:
        return ""
    return str(val)

def is_valid(s1, s2):
    return len(safe_str(s1).strip()) > 0 and len(safe_str(s2).strip()) > 0

def convert_to_xml(xlsx_path: str = r"C:\Users\kaede\Downloads\驯兽师联盟译名表.xlsx", output_path: str = "glossary.xml"):
    import warnings
    warnings.simplefilter("ignore")
    
    import openpyxl.styles.stylesheet
    import openpyxl.reader.excel
    orig_apply_stylesheet = openpyxl.styles.stylesheet.apply_stylesheet
    
    def safe_apply_stylesheet(archive, wb_obj):
        try:
            orig_apply_stylesheet(archive, wb_obj)
        except Exception as err:
            print(f"Warning: Stylesheet ignored due to error: {err}")
            
    openpyxl.styles.stylesheet.apply_stylesheet = safe_apply_stylesheet
    if hasattr(openpyxl.reader.excel, 'apply_stylesheet'):
        openpyxl.reader.excel.apply_stylesheet = safe_apply_stylesheet
        
    wb = openpyxl.load_workbook(xlsx_path, data_only=True, read_only=True)
    
    sections = []
    
    # 4. 数码兽及其技能名
    if "数码兽及其技能名" in wb.sheetnames:
        sheet = wb["数码兽及其技能名"]
        lines = []
        for row in sheet.iter_rows(min_row=2, values_only=True):
            r = [safe_str(x) for x in row]
            while len(r) < 13:
                r.append("")
                
            digimon_xml = f'    <Digimon JapaneseName="{r[0]}" ChineseName="{r[1]}">\n'
            digimon_xml += f'        <Level DigimonLevel="{r[2]}"/>\n'
            digimon_xml += '        <Skills>\n'
            
            if is_valid(r[3], r[4]):
                digimon_xml += f'            <Skill JapaneseName="{r[3]}" ChineseName="{r[4]}"/>\n'
            if is_valid(r[5], r[6]):
                digimon_xml += f'            <Skill JapaneseName="{r[5]}" ChineseName="{r[6]}"/>\n'
            if is_valid(r[7], r[8]):
                digimon_xml += f'            <Skill JapaneseName="{r[7]}" ChineseName="{r[8]}"/>\n'
            if is_valid(r[9], r[10]):
                digimon_xml += f'            <Skill JapaneseName="{r[9]}" ChineseName="{r[10]}"/>\n'
            if is_valid(r[11], r[11]):
                digimon_xml += f'            <Skill JapaneseName="{r[11]}" ChineseName="{r[11]}"/>\n'
            
            digimon_xml += '        </Skills>\n'
            digimon_xml += '    </Digimon>'
            lines.append(digimon_xml)
        if lines:
            sections.append("\n".join(lines))
            
    # 5. 人类及其他非数码兽角色名
    if "人类及其他非数码兽角色名" in wb.sheetnames:
        sheet = wb["人类及其他非数码兽角色名"]
        lines = []
        for row in sheet.iter_rows(min_row=2, values_only=True):
            r = [safe_str(x) for x in row]
            while len(r) < 6:
                r.append("")
            
            if is_valid(r[0], r[1]):
                lines.append(f'    <HumanCharacter JapaneseName="{r[0]}" ChineseName="{r[1]}"/>')
            if is_valid(r[2], r[3]):
                lines.append(f'    <HumanCharacter JapaneseName="{r[2]}" ChineseName="{r[3]}"/>')
            if is_valid(r[4], r[5]):
                lines.append(f'    <HumanCharacter JapaneseName="{r[4]}" ChineseName="{r[5]}"/>')
        if lines:
            sections.append("\n".join(lines))
            
    # 6. 地名、道具名及其他专有名词
    if "地名、道具名及其他专有名词" in wb.sheetnames:
        sheet = wb["地名、道具名及其他专有名词"]
        lines = []
        for row in sheet.iter_rows(min_row=2, values_only=True):
            r = [safe_str(x) for x in row]
            while len(r) < 9:
                r.append("")
                
            if is_valid(r[0], r[1]):
                lines.append(f'''    <Location Category="现实世界地名">\n        <Entry JapaneseName="{r[0]}" ChineseName="{r[1]}"/>\n    </Location>''')
            if is_valid(r[2], r[3]):
                lines.append(f'''    <Location Category="数码世界地名">\n        <Entry JapaneseName="{r[2]}" ChineseName="{r[3]}"/>\n    </Location>''')
            if is_valid(r[4], r[5]):
                lines.append(f'''    <Others>\n        <Entry JapaneseName="{r[4]}" ChineseName="{r[5]}"/>\n    </Others>''')
            if is_valid(r[6], r[7]):
                lines.append(f'''    <Idioms description="固定翻译">\n        <Entry JapaneseSentence="{r[6]}" ChineseSentence="{r[7]}" Comment="{r[8]}"/>\n    </Idioms>''')
        if lines:
            sections.append("\n".join(lines))
            
    # 7. 作品名
    if "作品名" in wb.sheetnames:
        sheet = wb["作品名"]
        lines = []
        for row in sheet.iter_rows(min_row=2, values_only=True):
            r = [safe_str(x) for x in row]
            while len(r) < 2:
                r.append("")
            if is_valid(r[0], r[1]):
                lines.append(f'    <Title JapaneseName="{r[0]}" ChineseName="{r[1]}"/>')
        if lines:
            sections.append("\n".join(lines))
            
    # 8. 4~7的内容以换行和<!--Split-->隔开
    inner_xml = "\n<!--Split-->\n".join(sections)
    
    # 1. 整个XML由<Glossary></Glossary>包裹
    final_xml = f"<Glossary>\n{inner_xml}\n</Glossary>"
    
    # 9. 保存到glossary.xml里面
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(final_xml)

if __name__ == "__main__":
    convert_to_xml()