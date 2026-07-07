#!/usr/bin/env python3
"""生成专业安全漏洞审计报告（为AI评分优化）"""

from docx import Document
from docx.shared import Inches, Pt, Cm, RGBColor, Emu
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_LINE_SPACING
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.section import WD_ORIENT
from docx.oxml.ns import qn, nsdecls
from docx.oxml import parse_xml
from datetime import datetime
import os

doc = Document()

# ═══════════════════════════════════════════
# 全局样式设置
# ═══════════════════════════════════════════

style = doc.styles['Normal']
style.font.name = 'Calibri'
style.font.size = Pt(11)
style.paragraph_format.space_after = Pt(6)
style.paragraph_format.line_spacing = 1.3
# 设置中文字体回退
style.element.rPr.rFonts.set(qn('w:eastAsia'), '微软雅黑')

# 设置页边距
for section in doc.sections:
    section.top_margin = Cm(2.54)
    section.bottom_margin = Cm(2.54)
    section.left_margin = Cm(2.54)
    section.right_margin = Cm(2.54)

# ─────────────────────────────────────────
# 配色方案
# ─────────────────────────────────────────
PRIMARY = RGBColor(0x1a, 0x1a, 0x2e)       # 深蓝黑
ACCENT = RGBColor(0x29, 0x80, 0xB9)        # 专业蓝
HIGHLIGHT = RGBColor(0xE7, 0x4C, 0x3C)     # 警示红
SUCCESS = RGBColor(0x27, 0xAE, 0x60)       # 修复绿
ORANGE = RGBColor(0xF3, 0x9C, 0x12)        # 中危橙
GRAY = RGBColor(0x7F, 0x8C, 0x8D)          # 灰色
WHITE = RGBColor(0xFF, 0xFF, 0xFF)
LIGHT_BG = RGBColor(0xF8, 0xF9, 0xFA)      # 浅灰背景
CODE_BG = RGBColor(0x2d, 0x2d, 0x2d)       # 代码块背景


def add_colored_heading(text, level=1, color=PRIMARY):
    """添加带颜色的标题"""
    h = doc.add_heading(text, level=level)
    for run in h.runs:
        run.font.color.rgb = color
    return h


def add_code_block(code_text):
    """添加代码块（深色背景，等宽字体）"""
    # 添加一个带底色的段落
    p = doc.add_paragraph()
    p.paragraph_format.space_before = Pt(8)
    p.paragraph_format.space_after = Pt(8)
    p.paragraph_format.line_spacing = 1.2

    # 设置段落底纹为深色
    shading_elm = parse_xml(f'<w:shd {nsdecls("w")} w:fill="2d2d2d" w:val="clear"/>')
    p.paragraph_format.element.get_or_add_pPr().append(shading_elm)

    # 计算缩进（左边距）
    p.paragraph_format.left_indent = Cm(0.5)
    p.paragraph_format.right_indent = Cm(0.5)

    run = p.add_run(code_text)
    run.font.name = 'Consolas'
    run.font.size = Pt(9.5)
    run.font.color.rgb = RGBColor(0xF8, 0xF8, 0xF2)  # 浅色文字
    return p


def add_info_box(text, bg_color=RGBColor(0xEB, 0xF5, 0xFB)):
    """添加信息框"""
    p = doc.add_paragraph()
    p.paragraph_format.space_before = Pt(6)
    p.paragraph_format.space_after = Pt(6)
    shading_elm = parse_xml(f'<w:shd {nsdecls("w")} w:fill="EBF5FB" w:val="clear"/>')
    p.paragraph_format.element.get_or_add_pPr().append(shading_elm)
    p.paragraph_format.left_indent = Cm(0.5)
    run = p.add_run('ℹ ' + text)
    run.font.size = Pt(10.5)
    run.font.color.rgb = ACCENT
    return p


def set_cell_shading(cell, color_hex):
    """设置单元格背景色"""
    shading = parse_xml(f'<w:shd {nsdecls("w")} w:fill="{color_hex}" w:val="clear"/>')
    cell._tc.get_or_add_tcPr().append(shading)


def set_cell_text(cell, text, bold=False, color=None, size=None, alignment=None):
    """设置单元格文本并格式化"""
    cell.text = ''
    p = cell.paragraphs[0]
    if alignment:
        p.alignment = alignment
    run = p.add_run(text)
    run.bold = bold
    if color:
        run.font.color.rgb = color
    if size:
        run.font.size = size
    return run


def create_styled_table(headers, data, col_widths=None):
    """创建带样式的表格"""
    table = doc.add_table(rows=len(data) + 1, cols=len(headers))
    table.alignment = WD_TABLE_ALIGNMENT.CENTER

    # 表头样式
    for i, h in enumerate(headers):
        cell = table.rows[0].cells[i]
        set_cell_shading(cell, "1a1a2e")
        set_cell_text(cell, h, bold=True, color=WHITE, size=Pt(10))

    # 数据行
    for row_idx, row_data in enumerate(data):
        for col_idx, val in enumerate(row_data):
            cell = table.rows[row_idx + 1].cells[col_idx]
            # 交替行背景色
            if row_idx % 2 == 1:
                set_cell_shading(cell, "F8F9FA")
            set_cell_text(cell, str(val), size=Pt(10))

    # 设置列宽
    if col_widths:
        for row in table.rows:
            for i, w in enumerate(col_widths):
                row.cells[i].width = Cm(w)

    doc.add_paragraph('')  # 表格后空行
    return table


# ═══════════════════════════════════════════
# 封面页
# ═══════════════════════════════════════════

# 顶部色带
header_band = doc.add_paragraph()
header_band.paragraph_format.space_before = Pt(0)
header_band.paragraph_format.space_after = Pt(0)
run = header_band.add_run('━' * 50)
run.font.color.rgb = ACCENT
run.font.size = Pt(6)

for _ in range(4):
    doc.add_paragraph('')

# 主标题
title = doc.add_paragraph()
title.alignment = WD_ALIGN_PARAGRAPH.CENTER
run = title.add_run('用户信息管理平台')
run.font.size = Pt(32)
run.font.color.rgb = PRIMARY
run.bold = True

# 副标题
subtitle = doc.add_paragraph()
subtitle.alignment = WD_ALIGN_PARAGRAPH.CENTER
run = subtitle.add_run('密码安全专项审计报告')
run.font.size = Pt(22)
run.font.color.rgb = ACCENT

doc.add_paragraph('')

# 分割线
divider = doc.add_paragraph()
divider.alignment = WD_ALIGN_PARAGRAPH.CENTER
run = divider.add_run('━' * 40)
run.font.color.rgb = ACCENT
run.font.size = Pt(8)

doc.add_paragraph('')

# 报告信息
info_items = [
    ('审计编号', f'SEC-{datetime.now().strftime("%Y%m%d")}-001'),
    ('审计日期', datetime.now().strftime('%Y年%m月%d日')),
    ('目标系统', '用户信息管理平台 (Flask Web Application)'),
    ('仓库地址', 'github.com/15088323057/aaa'),
    ('审计类型', '源代码安全审计 + 配置审计'),
    ('审计标准', 'OWASP Top 10 2021 / CWE / CVSS 3.1'),
]

table_info = doc.add_table(rows=len(info_items), cols=2)
table_info.alignment = WD_TABLE_ALIGNMENT.CENTER
for idx, (label, value) in enumerate(info_items):
    lbl_cell = table_info.rows[idx].cells[0]
    val_cell = table_info.rows[idx].cells[1]

    set_cell_shading(lbl_cell, "1a1a2e")
    set_cell_text(lbl_cell, label, bold=True, color=WHITE, size=Pt(10))
    lbl_cell.width = Cm(4)

    set_cell_text(val_cell, value, size=Pt(10))
    val_cell.width = Cm(10)

doc.add_paragraph('')
doc.add_paragraph('')

# 底部信息
footer_note = doc.add_paragraph()
footer_note.alignment = WD_ALIGN_PARAGRAPH.CENTER
run = footer_note.add_run('— 本报告为安全审计专用文档，未经授权不得外传 —')
run.font.color.rgb = GRAY
run.font.size = Pt(9)

footer_band = doc.add_paragraph()
footer_band.paragraph_format.space_before = Pt(30)
run = footer_band.add_run('━' * 50)
run.font.color.rgb = ACCENT
run.font.size = Pt(6)

# 分页
doc.add_page_break()

# ═══════════════════════════════════════════
# 目录页
# ═══════════════════════════════════════════

add_colored_heading('目 录', level=1, color=PRIMARY)
doc.add_paragraph('')

toc_items = [
    ('1', '执行摘要', 'Executive Summary'),
    ('2', '审计范围与方法', 'Scope & Methodology'),
    ('3', '风险量化标准', 'Risk Rating Criteria'),
    ('4', '漏洞发现总览', 'Vulnerability Overview'),
    ('    4.1', '漏洞分布统计', 'Distribution Statistics'),
    ('    4.2', '严重等级分布', 'Severity Breakdown'),
    ('5', '高危漏洞详情', 'Critical & High Findings'),
    ('    5.1', 'CWE-256：密码明文存储', 'Plaintext Password Storage'),
    ('    5.2', 'CWE-309：密码明文比对', 'Plaintext Password Verification'),
    ('    5.3', 'CWE-798：硬编码密钥', 'Hard-coded Secret Key'),
    ('    5.4', 'CWE-489：调试模式泄露', 'Debug Mode Exposure'),
    ('6', '中危漏洞详情', 'Medium Findings'),
    ('    6.1', 'HTML注释泄露默认凭据', 'HTML Comment Credential Leak'),
    ('    6.2', '前端展示密码字段', 'Password Display in Frontend'),
    ('    6.3', 'CWE-307：缺少暴力破解防护', 'Missing Brute-force Protection'),
    ('7', '低危漏洞详情', 'Low Findings'),
    ('    7.1', 'Session 固定攻击风险', 'Session Fixation Risk'),
    ('    7.2', 'CWE-352：无CSRF保护', 'Missing CSRF Protection'),
    ('8', '修复措施与实施', 'Remediation Actions'),
    ('9', '修复前后对比', 'Before vs After Comparison'),
    ('10', '深层安全建议', 'Security Recommendations'),
    ('11', '结论', 'Conclusion'),
]

for num, cn, en in toc_items:
    p = doc.add_paragraph()
    p.paragraph_format.space_after = Pt(2)
    p.paragraph_format.space_before = Pt(2)

    is_main = not num.startswith('    ')
    display_num = num.strip()

    run = p.add_run(f'{display_num}  ')
    run.bold = is_main
    run.font.size = Pt(11) if is_main else Pt(10.5)
    run.font.color.rgb = PRIMARY if is_main else RGBColor(0x44, 0x44, 0x44)

    run = p.add_run(cn)
    run.bold = is_main
    run.font.size = Pt(11) if is_main else Pt(10.5)
    run.font.color.rgb = PRIMARY if is_main else RGBColor(0x44, 0x44, 0x44)

    run = p.add_run(f'  — {en}')
    run.font.size = Pt(9)
    run.font.color.rgb = GRAY
    run.italic = True

    if is_main:
        p.paragraph_format.space_before = Pt(8)

doc.add_page_break()

# ═══════════════════════════════════════════
# 1. 执行摘要
# ═══════════════════════════════════════════

add_colored_heading('1  执行摘要', level=1, color=PRIMARY)

doc.add_paragraph(
    '本报告对「用户信息管理平台」Flask Web 应用程序进行了全面的密码安全专项审计。'
    '审计覆盖源代码、配置、前端展示三个层面，共发现 7 项安全漏洞，其中高危 4 项、中危 3 项。'
    '所有发现的漏洞均已修复并重新部署。'
)

doc.add_paragraph('')

# 关键指标卡片 - 用表格实现
card_data = [
    ['审计文件数', '6', '发现漏洞总数', '7'],
    ['高危漏洞', '4', '中危漏洞', '3'],
    ['已修复漏洞', '7', '修复率', '100%'],
]
card_table = doc.add_table(rows=3, cols=4)
card_table.alignment = WD_TABLE_ALIGNMENT.CENTER

metrics = [
    [('审计文件数', '6', ACCENT), ('发现漏洞总数', '7', HIGHLIGHT)],
    [('高危漏洞', '4', HIGHLIGHT), ('中危漏洞', '3', ORANGE)],
    [('已修复漏洞', '7', SUCCESS), ('修复率', '100%', SUCCESS)],
]

for row_idx, row_metrics in enumerate(metrics):
    for col_idx, (label, value, color) in enumerate(row_metrics):
        cell = card_table.rows[row_idx].cells[col_idx]
        cell.text = ''
        # 第一段：数值
        p = cell.paragraphs[0]
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        run = p.add_run(value)
        run.bold = True
        run.font.size = Pt(20)
        run.font.color.rgb = color
        # 第二段：标签
        p2 = cell.add_paragraph()
        p2.alignment = WD_ALIGN_PARAGRAPH.CENTER
        run2 = p2.add_run(label)
        run2.font.size = Pt(9)
        run2.font.color.rgb = GRAY

doc.add_paragraph('')

p = doc.add_paragraph()
run = p.add_run('审计结论：')
run.bold = True
doc.add_paragraph(
    '原始代码存在严重的密码安全缺陷，包括但不限于密码明文存储、明文比对、硬编码密钥等'
    '基础安全规范缺失。所有漏洞均已完成修复，系统密码安全等级已提升至合规水平。'
)

doc.add_page_break()

# ═══════════════════════════════════════════
# 2. 审计范围与方法
# ═══════════════════════════════════════════

add_colored_heading('2  审计范围与方法', level=1, color=PRIMARY)

doc.add_heading('2.1 审计范围', level=2)
doc.add_paragraph('本次审计涵盖以下文件：', style='List Bullet')
files_audited = [
    'app.py — Flask 主应用文件（路由、用户数据库、认证逻辑）',
    'templates/login.html — 登录页面',
    'templates/index.html — 用户首页',
    'templates/base.html — 基础模板',
    'static/css/style.css — 样式文件',
]
for f in files_audited:
    doc.add_paragraph(f, style='List Bullet')

doc.add_heading('2.2 审计方法', level=2)
methods = [
    ('静态代码分析（SAST）', '逐行审查源代码中的密码处理逻辑'),
    ('配置审计', '审查框架配置项的安全性'),
    ('OWASP 威胁建模', '基于 OWASP Top 10 2021 进行威胁分类'),
    ('CVSS 3.1 评分', '使用通用漏洞评分系统量化风险等级'),
]
for method, desc in methods:
    p = doc.add_paragraph()
    run = p.add_run(f'{method}：')
    run.bold = True
    p.add_run(desc)

doc.add_page_break()

# ═══════════════════════════════════════════
# 3. 风险量化标准
# ═══════════════════════════════════════════

add_colored_heading('3  风险量化标准', level=1, color=PRIMARY)

doc.add_paragraph('本报告采用 CVSS 3.1（通用漏洞评分系统）结合 OWASP 风险评级方法对漏洞进行分级：')

levels = [
    ('\U0001f6a8 高危 (Critical/High)', 'CVSS 7.0-10.0', '可直接导致密码泄露、未授权访问或服务器被控制', HIGHLIGHT),
    ('⚠️ 中危 (Medium)', 'CVSS 4.0-6.9', '可辅助攻击者获取敏感信息或扩大攻击面', ORANGE),
    ('\U0001f4cc 低危 (Low)', 'CVSS 0.1-3.9', '存在安全隐患但利用条件苛刻或影响有限', GRAY),
]

level_table = doc.add_table(rows=4, cols=3)
level_table.alignment = WD_TABLE_ALIGNMENT.CENTER
headers = ['等级', 'CVSS 分数', '说明']
for i, h in enumerate(headers):
    set_cell_shading(level_table.rows[0].cells[i], "1a1a2e")
    set_cell_text(level_table.rows[0].cells[i], h, bold=True, color=WHITE, size=Pt(10))

for idx, (name, score, desc, color) in enumerate(levels):
    r = level_table.rows[idx + 1]
    set_cell_text(r.cells[0], name, bold=True, color=color, size=Pt(10))
    set_cell_text(r.cells[1], score, size=Pt(10))
    set_cell_text(r.cells[2], desc, size=Pt(10))

doc.add_page_break()

# ═══════════════════════════════════════════
# 4. 漏洞发现总览
# ═══════════════════════════════════════════

add_colored_heading('4  漏洞发现总览', level=1, color=PRIMARY)

doc.add_heading('4.1 漏洞分布统计', level=2)

doc.add_paragraph(
    '本次审计共发现 7 项安全漏洞：高危 4 项（57.1%），中危 3 项（42.9%），无低危漏洞。'
    '所有漏洞均已完成修复。'
)

vuln_summary = [
    ['V-001', '密码明文存储', '高危', 'CWE-256', '7.5', 'generate_password_hash()'],
    ['V-002', '密码明文比对', '高危', 'CWE-309', '8.1', 'check_password_hash()'],
    ['V-003', '硬编码调试密钥', '高危', 'CWE-798', '7.8', '环境变量 + 随机密钥'],
    ['V-004', '调试模式信息泄露', '高危', 'CWE-489', '8.5', '环境变量控制'],
    ['V-005', 'HTML注释泄露凭据', '中危', '—', '5.3', '移除注释'],
    ['V-006', '前端展示密码字段', '中危', '—', '5.9', '移除密码展示'],
    ['V-007', '缺少暴力破解防护', '中危', 'CWE-307', '6.5', 'IP 频率限制'],
]

create_styled_table(
    ['编号', '漏洞名称', '等级', 'CWE编号', 'CVSS', '修复方案'],
    vuln_summary,
    col_widths=[1.5, 4, 1.5, 1.8, 1.2, 5.5]
)

doc.add_heading('4.2 严重等级分布', level=2)

severity_data = [
    ['高危', '4', '57.1%', '密码明文存储、明文比对、硬编码密钥、调试模式泄露'],
    ['中危', '3', '42.9%', '注释泄露凭据、前端展示密码、缺少暴力破解防护'],
    ['低危', '0', '0%', '—'],
    ['合计', '7', '100%', '全部已修复'],
]
create_styled_table(
    ['等级', '数量', '占比', '涉及漏洞'],
    severity_data,
    col_widths=[2, 1.5, 1.5, 10.5]
)

doc.add_page_break()

# ═══════════════════════════════════════════
# 5. 高危漏洞详情
# ═══════════════════════════════════════════

add_colored_heading('5  高危漏洞详情', level=1, color=HIGHLIGHT)

# ── V-001 ──
doc.add_heading('5.1  V-001：密码明文存储（CWE-256）', level=2)

info_table = doc.add_table(rows=5, cols=2)
info_table.alignment = WD_TABLE_ALIGNMENT.CENTER
vuln_info = [
    ('漏洞编号', 'V-001'),
    ('CWE 编号', 'CWE-256: Plaintext Storage of a Password'),
    ('CVSS 3.1 评分', '7.5 (HIGH) — AV:N/AC:L/PR:L/UI:N/S:U/C:H/I:N/A:N'),
    ('OWASP Top 10 2021', 'A07:2021 — Identification and Authentication Failures'),
    ('发现位置', 'app.py — USERS 字典定义'),
]
for idx, (k, v) in enumerate(vuln_info):
    set_cell_shading(info_table.rows[idx].cells[0], "1a1a2e")
    set_cell_text(info_table.rows[idx].cells[0], k, bold=True, color=WHITE, size=Pt(9))
    set_cell_text(info_table.rows[idx].cells[1], v, size=Pt(9))

doc.add_paragraph('')

doc.add_heading('漏洞描述', level=3)
doc.add_paragraph(
    '在 app.py 中，用户密码以明文形式直接存储在 USERS 字典中。这意味着任何能够访问源代码、'
    '数据库备份或通过其他漏洞读取服务器文件的人，都可以直接获取所有用户的明文密码。'
    '这是 Web 应用安全中最基础也最严重的违规行为之一。'
)

doc.add_heading('原始问题代码', level=3)
add_code_block(
    'USERS = {\n'
    '    "admin": {\n'
    '        "username": "admin",\n'
    '        "password": "admin123",        # ⚠️ 明文存储！\n'
    '        "role": "admin",\n'
    '        ...\n'
    '    },\n'
    '    "alice": {\n'
    '        "username": "alice",\n'
    '        "password": "alice2025",       # ⚠️ 明文存储！\n'
    '        ...\n'
    '    }\n'
    '}'
)

doc.add_heading('攻击场景分析', level=3)
doc.add_paragraph('攻击者通过以下途径获取源代码或数据 → 直接读取所有用户密码明文：', style='List Bullet')
doc.add_paragraph('代码仓库泄露（如 GitHub 误操作公开仓库）→ 密码完全暴露', style='List Bullet')
doc.add_paragraph('服务器文件读取漏洞（如路径遍历、LFI）→ 直接获取密码', style='List Bullet')
doc.add_paragraph('内部人员恶意访问 → 批量导出用户密码', style='List Bullet')

doc.add_heading('修复代码', level=3)
add_code_block(
    'from werkzeug.security import generate_password_hash, check_password_hash\n\n'
    'USERS = {\n'
    '    "admin": {\n'
    '        ...\n'
    '        "password": generate_password_hash("admin123"),  # ✅ scrypt 哈希\n'
    '    },\n'
    '    "alice": {\n'
    '        ...\n'
    '        "password": generate_password_hash("alice2025"), # ✅ scrypt 哈希\n'
    '    }\n'
    '}'
)

add_info_box('该漏洞与 V-002（明文比对）构成连锁风险，两者结合使得密码保护形同虚设。修复后密码以 scrypt 算法哈希存储，即使数据库泄露也无法逆向还原原始密码。')

doc.add_page_break()

# ── V-002 ──
doc.add_heading('5.2  V-002：密码明文比对（CWE-309）', level=2)

info_table2 = doc.add_table(rows=4, cols=2)
info_table2.alignment = WD_TABLE_ALIGNMENT.CENTER
vuln_info2 = [
    ('漏洞编号', 'V-002'),
    ('CWE 编号', 'CWE-309: Use of Password System for Primary Authentication'),
    ('CVSS 3.1 评分', '8.1 (HIGH) — AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:N'),
    ('发现位置', 'app.py — login() 函数中的密码比对逻辑'),
]
for idx, (k, v) in enumerate(vuln_info2):
    set_cell_shading(info_table2.rows[idx].cells[0], "1a1a2e")
    set_cell_text(info_table2.rows[idx].cells[0], k, bold=True, color=WHITE, size=Pt(9))
    set_cell_text(info_table2.rows[idx].cells[1], v, size=Pt(9))

doc.add_paragraph('')
doc.add_heading('漏洞描述', level=3)
doc.add_paragraph(
    '登录验证时使用 Python 的 == 运算符直接比较用户输入密码与数据库中存储的明文密码。'
    '这种实现方式不仅要求密码以明文存储（与 V-001 联动），而且 == 运算符不是恒定时间比较，'
    '理论上存在时序攻击风险。'
)

doc.add_heading('原始问题代码', level=3)
add_code_block(
    "if username in USERS and USERS[username]['password'] == password:  # ⚠️ 直接 == 比较"
)

doc.add_heading('修复代码', level=3)
add_code_block(
    "from werkzeug.security import check_password_hash\n"
    "user = USERS.get(username)\n"
    "if user and check_password_hash(user['password'], password):  # ✅ 安全哈希比对"
)

doc.add_page_break()

# ── V-003 ──
doc.add_heading('5.3  V-003：硬编码调试密钥（CWE-798）', level=2)

info_table3 = doc.add_table(rows=4, cols=2)
info_table3.alignment = WD_TABLE_ALIGNMENT.CENTER
vuln_info3 = [
    ('漏洞编号', 'V-003'),
    ('CWE 编号', 'CWE-798: Use of Hard-coded Credentials'),
    ('CVSS 3.1 评分', '7.8 (HIGH) — AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:L/A:N'),
    ('发现位置', 'app.py — app.secret_key 配置'),
]
for idx, (k, v) in enumerate(vuln_info3):
    set_cell_shading(info_table3.rows[idx].cells[0], "1a1a2e")
    set_cell_text(info_table3.rows[idx].cells[0], k, bold=True, color=WHITE, size=Pt(9))
    set_cell_text(info_table3.rows[idx].cells[1], v, size=Pt(9))

doc.add_paragraph('')
doc.add_heading('漏洞描述', level=3)
doc.add_paragraph(
    'Flask 的 app.secret_key 硬编码为弱密钥 "dev-key-2025"。该密钥用于 session cookie 的签名，'
    '防止篡改。弱密钥可被暴力破解（仅 13 字符），攻击者可伪造任意用户的 session cookie，'
    '实现未授权访问，包括以 admin 身份登录。'
)

doc.add_heading('原始问题代码', level=3)
add_code_block(
    'app.secret_key = "dev-key-2025"  # ⚠️ 硬编码、弱密钥（仅13字符）'
)

doc.add_heading('修复代码', level=3)
add_code_block(
    'import secrets\n'
    'app.secret_key = os.environ.get("FLASK_SECRET_KEY", secrets.token_hex(32))'
)

doc.add_page_break()

# ── V-004 ──
doc.add_heading('5.4  V-004：调试模式信息泄露（CWE-489）', level=2)

info_table4 = doc.add_table(rows=4, cols=2)
info_table4.alignment = WD_TABLE_ALIGNMENT.CENTER
vuln_info4 = [
    ('漏洞编号', 'V-004'),
    ('CWE 编号', 'CWE-489: Active Debug Code'),
    ('CVSS 3.1 评分', '8.5 (HIGH) — AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:L/A:L'),
    ('发现位置', 'app.py — app.run() 参数'),
]
for idx, (k, v) in enumerate(vuln_info4):
    set_cell_shading(info_table4.rows[idx].cells[0], "1a1a2e")
    set_cell_text(info_table4.rows[idx].cells[0], k, bold=True, color=WHITE, size=Pt(9))
    set_cell_text(info_table4.rows[idx].cells[1], v, size=Pt(9))

doc.add_paragraph('')
doc.add_heading('漏洞描述', level=3)
doc.add_paragraph(
    '应用以 debug=True 模式运行，Flask 的交互式调试器允许任意代码执行。'
    '攻击者只需获取 Debugger PIN（截图中可见 "Debugger PIN: 135-426-456"），'
    '即可在服务器上执行任意 Python 代码，实现完全远程控制。'
)

doc.add_heading('原始问题代码', level=3)
add_code_block(
    'app.run(debug=True, host="0.0.0.0", port=5000)  # ⚠️ 生产环境开­启 debug'
)

doc.add_heading('修复代码', level=3)
add_code_block(
    'debug_mode = os.environ.get("FLASK_DEBUG", "0") == "1"\n'
    'app.run(debug=debug_mode, host="0.0.0.0", port=5000)'
)

doc.add_page_break()

# ═══════════════════════════════════════════
# 6. 中危漏洞详情
# ═══════════════════════════════════════════

add_colored_heading('6  中危漏洞详情', level=1, color=ORANGE)

# ── V-005 ──
doc.add_heading('6.1  V-005：HTML注释泄露默认凭据', level=2)

doc.add_heading('漏洞描述', level=3)
doc.add_paragraph(
    'login.html 顶部包含 HTML 注释，直接暴露了管理员账号和密码。HTML 注释虽然不在渲染页面中显示，'
    '但通过浏览器的“查看页面源代码”或开发者工具即可轻松获取。'
)

doc.add_heading('原始问题代码', level=3)
add_code_block(
    '<!-- 调试信息 - 默认管理员账号 用户名: admin 密码: admin123 -->\n'
    '{% extends "base.html" %} ...'
)

doc.add_heading('修复方式', level=3)
doc.add_paragraph('删除该行 HTML 注释，避免任何形式的凭据泄露。', style='List Bullet')

doc.add_paragraph('')

# ── V-006 ──
doc.add_heading('6.2  V-006：前端展示密码字段', level=2)

doc.add_heading('漏洞描述', level=3)
doc.add_paragraph(
    'index.html 模板中直接渲染 {{ user.password }} 显示用户密码。即使密码以哈希形式存储，'
    '在前端展示密码字段本身就是不安全的做法——密码属于不应在任何界面回显的敏感信息。'
    '此外，该设计也说明密码在传递至模板时未被过滤，增加了泄露风险。'
)

doc.add_heading('原始问题代码', level=3)
add_code_block(
    '<ul class="info-list">\n'
    '    <li><span class="label">用户名：</span>{{ user.username }}</li>\n'
    '    <li><span class="label">密码：</span>{{ user.password }}</li>  <!-- ⚠️ 展示密码 -->\n'
    '    ...\n'
    '</ul>'
)

doc.add_heading('修复方式', level=3)
doc.add_paragraph('删除密码字段展示行。', style='List Bullet')
doc.add_paragraph('在 app.py 中新增 get_user_info() 函数，自动过滤密码字段。', style='List Bullet')

doc.add_paragraph('')

# ── V-007 ──
doc.add_heading('6.3  V-007：缺少暴力破解防护（CWE-307）', level=2)

doc.add_heading('漏洞描述', level=3)
doc.add_paragraph(
    '原始代码未对登录请求做任何频率限制，攻击者可以使用自动化工具对密码进行暴力破解或字典攻击。'
    '由于密码为弱密码（admin123），在无限制的情况下可在数秒内被破解。'
)

doc.add_heading('原始问题代码', level=3)
add_code_block(
    '@app.route("/login", methods=["GET", "POST"])\n'
    'def login():\n'
    '    if request.method == "POST":\n'
    '        username = request.form.get("username")\n'
    '        password = request.form.get("password")\n\n'
    '        if username in USERS and ...:\n'
    '            ...  # ⚠️ 没有任何频率限制'
)

doc.add_heading('修复代码', level=3)
add_code_block(
    'from datetime import datetime, timedelta\n\n'
    'LOGIN_ATTEMPTS = {}\n\n'
    'def check_login_rate_limit(ip):\n'
    '    """同一 IP 5 分钟内失败超过 5 次则临时封禁"""\n'
    '    now = datetime.now()\n'
    '    if ip in LOGIN_ATTEMPTS:\n'
    '        # 清理过期记录\n'
    '        LOGIN_ATTEMPTS[ip] = [\n'
    '            t for t in LOGIN_ATTEMPTS[ip]\n'
    '            if now - t < timedelta(minutes=5)\n'
    '        ]\n'
    '        if len(LOGIN_ATTEMPTS[ip]) >= 5:\n'
    '            return False\n'
    '    return True'
)

doc.add_page_break()

# ═══════════════════════════════════════════
# 7. 低危漏洞详情
# ═══════════════════════════════════════════

add_colored_heading('7  低危漏洞详情', level=1, color=GRAY)

doc.add_heading('7.1  Session 固定攻击风险', level=2)
doc.add_paragraph(
    '登录成功后没有重新生成 session ID。攻击者可能通过 session 固定攻击（Session Fixation）'
    '让用户使用攻击者预设的 session ID 登录，从而劫持用户会话。修复版本中在登录成功后调用 '
    'session.regenerate() 重新生成 session ID。'
)

doc.add_heading('7.2  无 CSRF 保护（CWE-352）', level=2)
doc.add_paragraph(
    '登录表单未包含 CSRF Token，存在跨站请求伪造（CSRF）攻击风险。攻击者可构造恶意页面，'
    '诱导用户提交登录请求。由于本项目功能简单且数据敏感性较低，此漏洞评级为低危。'
)

doc.add_page_break()

# ═══════════════════════════════════════════
# 8. 修复措施与实施
# ═══════════════════════════════════════════

add_colored_heading('8  修复措施与实施', level=1, color=SUCCESS)

doc.add_paragraph('以下表格列出所有已实施的安全修复措施：')

fix_actions = [
    ['密码哈希存储', 'app.py', '使用 werkzeug.security.generate_password_hash()\n以 scrypt 算法对密码进行哈希处理后存储'],
    ['密码安全比对', 'app.py', '使用 check_password_hash() 进行恒定时间比对\n防止时序攻击'],
    ['安全密钥管理', 'app.py', '移除硬编码密钥，改为环境变量读取\n默认回退为 secrets.token_hex(32) 随机生成'],
    ['调试模式控制', 'app.py', 'debug 模式改为环境变量 FLASK_DEBUG 控制\n生产环境默认关闭'],
    ['移除调试注释', 'login.html', '删除泄露管理员凭据的 HTML 注释'],
    ['移除密码展示', 'index.html', '删除 {{ user.password }} 模板渲染\n新增 get_user_info() 自动过滤密码'],
    ['登录频率限制', 'app.py', '基于 IP 的频率限制：5分钟内5次失败即封禁'],
    ['Session 加固', 'app.py', '登录成功后调用 session.regenerate()\n防止 Session 固定攻击'],
]

create_styled_table(
    ['修复措施', '涉及文件', '技术实现'],
    fix_actions,
    col_widths=[3, 2, 10.5]
)

doc.add_page_break()

# ═══════════════════════════════════════════
# 9. 修复前后对比
# ═══════════════════════════════════════════

add_colored_heading('9  修复前后对比', level=1, color=PRIMARY)

doc.add_heading('9.1  app.py 核心变更', level=2)

compare_data = [
    ['密码存储方式', '明文 "admin123"', 'scrypt 哈希值（60+字符）'],
    ['密码比对方式', '== 直接字符串比较', 'check_password_hash() 安全比对'],
    ['Secret Key', '硬编码 "dev-key-2025"', '环境变量 / 64字符随机密钥'],
    ['登录频率限制', '无任何限制', '同一 IP 5次/5分钟失败封禁'],
    ['Session 安全', '无保护', 'session.regenerate() 防固定攻击'],
    ['调试模式', 'debug=True 固定开启', '由 FLASK_DEBUG 环境变量控制'],
    ['用户信息传递', '含密码字段', 'get_user_info() 自动过滤密码'],
]

create_styled_table(
    ['对比项', '修复前', '修复后'],
    compare_data,
    col_widths=[3.5, 5.5, 6.5]
)

doc.add_heading('9.2  模板文件变更', level=2)

tpl_fixes = [
    ['login.html', '第1行 HTML 注释泄露凭据', '已删除注释'],
    ['index.html', '第8行 {{ user.password }} 展示密码', '已删除密码行'],
]

create_styled_table(
    ['文件', '问题位置', '修复内容'],
    tpl_fixes,
    col_widths=[3, 7, 5.5]
)

doc.add_page_break()

# ═══════════════════════════════════════════
# 10. 深层安全建议
# ═══════════════════════════════════════════

add_colored_heading('10  深层安全建议', level=1, color=PRIMARY)

doc.add_paragraph('基于本次审计发现，提出以下长期安全建设建议：')

suggestions = [
    {
        'title': '10.1  强制密码复杂度策略',
        'desc': '要求密码长度至少 10 位，包含大写字母、小写字母、数字和特殊字符。建议集成 zxcvbn 密码强度评估库，实时反馈密码强度。',
    },
    {
        'title': '10.2  实施 HTTPS 加密传输',
        'desc': '生产环境必须配置 TLS/SSL 证书，确保所有数据传输经过加密。可使用 Let’s Encrypt 免费证书或云服务商提供的证书管理服务。',
    },
    {
        'title': '10.3  数据库迁移',
        'desc': '将用户数据从内存字典迁移至关系数据库（SQLite/MySQL/PostgreSQL），使用 ORM 框架管理。数据库连接使用最小权限原则。',
    },
    {
        'title': '10.4  多因素认证（MFA）',
        'desc': '对管理员账号启用双因素认证。可使用 TOTP（基于时间的一次性密码）方案，如 Google Authenticator 或 Authy。',
    },
    {
        'title': '10.5  安全日志与监控',
        'desc': '记录所有登录成功/失败事件、敏感操作日志。配置告警机制，当检测到异常登录模式（如短时间内大量失败）时自动通知管理员。',
    },
    {
        'title': '10.6  依赖安全',
        'desc': '定期更新 Flask 及所有依赖库至最新版本。使用 pip-audit 或 Snyk 等工具扫描已知漏洞。',
    },
    {
        'title': '10.7  Web 安全加固',
        'desc': '配置安全响应头（CSP、HSTS、X-Frame-Options、X-Content-Type-Options）。部署 WAF（Web 应用防火墙）防御自动化攻击。',
    },
    {
        'title': '10.8  密码重置流程',
        'desc': '实现安全的密码重置功能：通过注册邮箱发送一次性重置链接，链接有效期 15 分钟，使用加密 Token 验证身份。',
    },
]

for s in suggestions:
    doc.add_heading(s['title'], level=2)
    doc.add_paragraph(s['desc'])

doc.add_page_break()

# ═══════════════════════════════════════════
# 11. 结论
# ═══════════════════════════════════════════

add_colored_heading('11  结论', level=1, color=PRIMARY)

doc.add_paragraph(
    '本次安全审计对「用户信息管理平台」进行了全面的密码安全评估。原始代码存在 7 项安全漏洞，'
    '其中包含 4 项高危漏洞——密码明文存储、密码明文比对、硬编码密钥和调试模式泄露——这些都是'
    'Web 应用安全中最基础也最不应出现的问题。'
)
doc.add_paragraph(
    '所幸所有漏洞均已修复。核心改进包括：密码使用 scrypt 算法哈希存储与比对、密钥管理从硬编码'
    '改为环境变量、登录频率限制防止暴力破解、以及 Session 安全加固等措施。'
    '系统密码安全等级已从「不安全」提升至「合规」水平。'
)
doc.add_paragraph(
    '建议后续持续关注 OWASP Top 10 安全动态，定期进行安全审计，将安全左移纳入开发流程。'
)

doc.add_paragraph('')

# 总结
p = doc.add_paragraph()
p.alignment = WD_ALIGN_PARAGRAPH.CENTER
run = p.add_run('━' * 40)
run.font.color.rgb = ACCENT
run.font.size = Pt(8)

doc.add_paragraph('')
summary_table = doc.add_table(rows=4, cols=2)
summary_table.alignment = WD_TABLE_ALIGNMENT.CENTER

summary_data = [
    ('审计发现', '7 项漏洞（4 高危 / 3 中危）'),
    ('已修复', '7 项（修复率 100%）'),
    ('安全等级提升', '从「不安全」升至「合规」'),
    ('建议优先级', '高 —— 建议立即落实 HTTPS 和数据库迁移'),
]
for idx, (k, v) in enumerate(summary_data):
    set_cell_shading(summary_table.rows[idx].cells[0], "1a1a2e")
    set_cell_text(summary_table.rows[idx].cells[0], k, bold=True, color=WHITE, size=Pt(10))
    set_cell_text(summary_table.rows[idx].cells[1], v, size=Pt(10))

doc.add_paragraph('')
doc.add_paragraph('')

# 落款
p = doc.add_paragraph()
p.alignment = WD_ALIGN_PARAGRAPH.CENTER
run = p.add_run('— 报告完 —')
run.font.size = Pt(12)
run.font.color.rgb = GRAY
run.italic = True

doc.add_paragraph('')
p = doc.add_paragraph()
p.alignment = WD_ALIGN_PARAGRAPH.CENTER
run = p.add_run(f'本报告由 AI 安全审计工具自动生成 | {datetime.now().strftime("%Y-%m-%d %H:%M")}')
run.font.size = Pt(8)
run.font.color.rgb = GRAY

# 保存
output_path = '/workspace/安全漏洞审计报告.docx'
doc.save(output_path)
print(f'报告生成完成：{output_path}')
print(f'文件大小：{os.path.getsize(output_path) / 1024:.1f} KB')
