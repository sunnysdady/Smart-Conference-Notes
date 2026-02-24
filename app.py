import streamlit as st
import requests
import json
import os
import re
import whisper
import time
from dotenv import load_dotenv

# ===================== 1. 基础配置 =====================
load_dotenv()
st.set_page_config(page_title="飞书原生看板-最终破壁版", page_icon="🎯", layout="wide")

APP_ID = "cli_a916f070b0f8dcd6"
APP_SECRET = "gHOYZxXsoTXpmsnyf37C5dqcN4tOkibW"
QWEN_API_KEY = "sk-ecb46034c430477e9c9a4b4fd6589742"

# ===================== 2. 飞书底层 API 封装 =====================

def get_feishu_token():
    try:
        url = "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal"
        res = requests.post(url, json={"app_id": APP_ID, "app_secret": APP_SECRET}, timeout=10)
        return res.json().get("tenant_access_token")
    except:
        return None

def create_feishu_doc(title):
    token = get_feishu_token()
    if not token: return None
    url = "https://open.feishu.cn/open-apis/docx/v1/documents"
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    safe_title = str(title).strip() if title else "智能会议看板"
    res = requests.post(url, headers=headers, json={"title": safe_title})
    return res.json().get("data", {}).get("document", {}).get("document_id")

def build_100pct_safe_blocks(data):
    """
    【最终视觉引擎】
    利用安全的色块实现视觉看板。
    1=红, 2=橙, 3=黄, 4=绿, 7=灰
    """
    blocks = []
    
    def safe_text(content):
        return str(content).replace('\n', ' ').strip() if content else "无"

    # 空行生成器（飞书标准空行）
    def empty_line():
        return {"block_type": 2, "text": {"elements": []}}

    # 1. 标题与基础信息
    blocks.append({"block_type": 3, "heading1": {"elements": [{"text_run": {"content": safe_text(data.get("title", "智能纪要"))}}]}})
    blocks.append({"block_type": 2, "text": {"elements": [{"text_run": {"content": f"📅 {safe_text(data.get('date', '近期'))} | AI智能提取", "text_element_style": {"text_color": 7}}}]}})
    blocks.append(empty_line())

    # 2. 重点项目
    blocks.append({"block_type": 4, "heading2": {"elements": [{"text_run": {"content": "📊 重点项目概览"}}]}})
    for proj in data.get("projects", []):
        status = safe_text(proj.get("status", "进行中"))
        name = safe_text(proj.get("name", "未命名项目"))
        
        # 视觉映射
        tc, bgc = 7, 7 # 默认灰色
        if "正常" in status or "完成" in status: tc, bgc = 4, 4
        elif "风险" in status or "滞销" in status or "待" in status: tc, bgc = 1, 1
        elif "优化" in status or "讨论" in status: tc, bgc = 2, 2
            
        blocks.append({
            "block_type": 2,
            "text": {"elements": [
                {"text_run": {"content": f" ❖ {name}   ", "text_element_style": {"bold": True}}},
                {"text_run": {"content": f" {status} ", "text_element_style": {"text_color": tc, "background_color": bgc, "bold": True}}}
            ]}
        })
        for detail in proj.get("details", []):
            blocks.append({"block_type": 12, "bullet": {"elements": [{"text_run": {"content": safe_text(detail)}}]}})
    blocks.append(empty_line())

    # 3. 运营工作
    blocks.append({"block_type": 4, "heading2": {"elements": [{"text_run": {"content": "🗓️ 运营工作跟进"}}]}})
    for op in data.get("operations", []):
        status = safe_text(op.get("status", "待定"))
        tc, bgc = (4,4) if "完成" in status else ((1,1) if "待" in status else (2,2))
        
        blocks.append({
            "block_type": 12,
            "bullet": {"elements": [
                {"text_run": {"content": f"{safe_text(op.get('category', '分类'))}   ", "text_element_style": {"bold": True}}},
                {"text_run": {"content": f" {status} ", "text_element_style": {"text_color": tc, "background_color": bgc, "bold": True}}},
                {"text_run": {"content": f"  |  操作: {safe_text(op.get('content', '无'))}  |  负责人: {safe_text(op.get('owner', '待定'))}", "text_element_style": {"text_color": 7}}}
            ]}
        })
    blocks.append(empty_line())

    # 4. 下一步计划
    blocks.append({"block_type": 4, "heading2": {"elements": [{"text_run": {"content": "🚀 下一步计划"}}]}})
    blocks.append({
        "block_type": 2,
        "text": {"elements": [
            {"text_run": {"content": f" 💡 {safe_text(data.get('next_steps', '暂无'))} ", "text_element_style": {"bold": True, "background_color": 3}}}
        ]}
    })
    blocks.append(empty_line())

    # 5. 核心决策
    blocks.append({"block_type": 4, "heading2": {"elements": [{"text_run
