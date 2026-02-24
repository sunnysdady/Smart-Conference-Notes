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
st.set_page_config(page_title="飞书智能纪要：原生看板引擎", page_icon="🎯", layout="wide")

APP_ID = "cli_a916f070b0f8dcd6"
APP_SECRET = "gHOYZxXsoTXpmsnyf37C5dqcN4tOkibW"
QWEN_API_KEY = "sk-ecb46034c430477e9c9a4b4fd6589742"

# ===================== 2. 飞书开放平台底层 API =====================

def get_feishu_token():
    url = "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal"
    res = requests.post(url, json={"app_id": APP_ID, "app_secret": APP_SECRET})
    return res.json().get("tenant_access_token")

def create_feishu_doc(title):
    token = get_feishu_token()
    url = "https://open.feishu.cn/open-apis/docx/v1/documents"
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    res = requests.post(url, headers=headers, json={"title": title})
    return res.json().get("data", {}).get("document", {}).get("document_id")

def build_native_feishu_blocks(data):
    """
    【核心渲染引擎】将 JSON 数据 1:1 映射为飞书原生带颜色的 Blocks
    """
    blocks = []
    
    # 1. 标题与基础信息
    blocks.append({"block_type": 3, "heading1": {"elements": [{"text_run": {"content": data.get("title", "智能纪要")}}]}})
    blocks.append({"block_type": 2, "text": {"elements": [{"text_run": {"content": f"📅 录音时间：{data.get('date', '未提及')}\n💡 智能纪要由AI生成，请谨慎甄别后使用", "text_element_style": {"text_color": 7}}}]}})
    
    # 2. 重点项目 (原生色块还原)
    blocks.append({"block_type": 4, "heading2": {"elements": [{"text_run": {"content": "📊 重点项目概览"}}]}})
    for proj in data.get("projects", []):
        status = proj.get("status", "")
        # 飞书原生色号映射: 4=绿, 1=红, 2=橙 (字体色); 14=浅绿, 11=浅红, 12=浅橙 (背景色)
        if "正常" in status or "完成" in status:
            tc, bgc, icon = 4, 14, "🟢"
        elif "风险" in status or "待" in status:
            tc, bgc, icon = 1, 11, "🔴"
        else:
            tc, bgc, icon = 2, 12, "🟠"
            
        # 构造带背景色的状态标签
        blocks.append({
            "block_type": 2,
            "text": {"elements": [
                {"text_run": {"content": f" ❖ {proj.get('name', '')}   ", "text_element_style": {"bold": True, "text_color": 5}}},
                {"text_run": {"content": f" {icon} {status} ", "text_element_style": {"text_color": tc, "background_color": bgc, "bold": True}}}
            ]}
        })
        # 项目细节
        for detail in proj.get("details", []):
            blocks.append({"block_type": 12, "bullet": {"elements": [{"text_run": {"content": detail}}]}})

    # 3. 运营工作跟进 (结构化清单模拟表格)
    blocks.append({"block_type": 4, "heading2": {"elements": [{"text_run": {"content": "📅 运营工作跟进"}}]}})
    for op in data.get("operations", []):
        status = op.get("status", "")
        tc, bgc, icon = (4,14,"🟢") if "完成" in status else ((1,11,"🔴") if "待" in status else (2,12,"🟠"))
        blocks.append({
            "block_type": 12,
            "bullet": {"elements": [
                {"text_run": {"content": f"{op.get('category', '')}   ", "text_element_style": {"bold": True}}},
                {"text_run": {"content": f" {icon} {status} ", "text_element_style": {"text_color": tc, "background_color": bgc, "bold": True}}},
                {"text_run": {"content": f"  |  负责人：{op.get('owner', '')}  |  操作：{op.get('content', '')}", "text_element_style": {"text_color": 7}}}
            ]}
        })

    # 4. 下一步计划 (醒目高亮)
    blocks.append({"block_type": 4, "heading2": {"elements": [{"text_run": {"content": "🚀 下一步计划"}}]}})
    blocks.append({"block_type": 2, "text": {"elements": [{"text_run": {"content": "💡 " + data.get("next_steps", ""), "text_element_style": {"bold": True, "background_color": 13}}}]}})

    # 5. 详细章节
    blocks.append({"block_type": 4, "heading2": {"elements": [{"text_run": {"content": "⏱️ 详细会议内容"}}]}})
    for chap in data.get("chapters", []):
        blocks.append({
            "block_type": 2, 
            "text": {"elements": [{"text_run": {"content": f"[{chap.get('time', '')}] {chap.get('title', '')}", "text_element_style": {"bold": True, "text_color": 5}}}]}
        })
        blocks.append({"block_type": 12, "bullet": {"elements": [{"text_run": {"content": chap.get("summary", ""), "text_element_style": {"text_color": 7}}}]}})

    # 6. 决策与金句
    blocks.append({"block_type": 4, "heading2": {"elements": [{"text_run": {"content": "🎯 关键决策与金句"}}]}})
    for dec in data.get("decisions", []):
        blocks.append({"block_type": 12, "bullet": {"elements": [{"text_run": {"content": f"决策: {dec.get('problem')} -> {dec.get('solution')}", "text_element_style": {"bold": True}}}]}})
    for quote in data.get("quotes", []):
        blocks.append({"block_type": 12, "bullet": {"elements": [{"text_run": {"content": f"「{quote.get('text')}」 —— {quote.get('speaker')}", "text_element_style": {"text_color": 7, "italic": True}}}]}})

    return blocks

def push_blocks_to_feishu(doc_id, blocks):
    token = get_feishu_token()
    url = f"https://open.feishu.cn/open-apis/docx/v1/documents/{doc_id}/blocks/0/children"
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    for i in range(0, len(blocks), 40):
        requests.post(url, headers=headers, json={"children": blocks[i:i+40], "index": -1})
    return f"https://bytedance.feishu.cn/docx/{doc_id}"

# ===================== 3. AI 引擎与逻辑 =====================

@st.cache_resource
def load_model():
    return whisper.load_model("base")

def generate_json_summary(content):
    """强制通义千问输出 JSON 格式，以便精准提取各模块数据"""
    url = "https://dashscope.aliyuncs.com/api/v1/services/aigc/text-generation/generation"
    headers = {"Authorization": f"Bearer {QWEN_API_KEY}", "Content-Type": "application/json"}
    
    prompt = f"""
    你是飞书智能秘书。请根据转写文本提取信息，并严格且仅输出 JSON 格式数据。
    JSON 必须包含以下结构：
    {{
        "title": "会议主题", "date": "XXXX年XX月XX日",
        "projects": [{{"name": "项目名", "status": "正常推进/需要优化/存在风险", "details": ["细节1", "细节2"]}}],
        "operations": [{{"category": "类别", "content": "具体操作", "owner": "负责人", "status": "已完成/待处理"}}],
        "next_steps": "下一步计划描述",
        "chapters": [{{"time": "00:01", "title": "章节标题", "summary": "章节内容"}}],
        "decisions": [{{"problem": "问题", "solution": "方案", "reason": "依据"}}],
        "quotes": [{{"speaker": "说话人", "text": "原话", "analysis": "分析"}}]
    }}
    转录原文：{content[:25000]}
    """
    
    payload = {"model": "qwen-max", "input": {"messages": [{"role": "user", "content": prompt}]}, "parameters": {"result_format": "text"}}
    try:
        res = requests.post(url, headers=headers, json=payload, timeout=90)
        res_text = res.json()["output"]["text"]
        
        # 安全提取 JSON 字符串
        json_match = re.search(r'\{.*\}', res_text, re.DOTALL)
        if json_match:
            return json.loads(json_match.group(0))
        else:
            st.error("AI 未返回标准 JSON 格式。")
            return None
    except Exception as e:
        st.error(f"AI 生成解析失败: {e}")
        return None

# ===================== 4. UI 工作流 =====================

st.title("🎯 飞书智能纪要：原生看板渲染引擎")
st.info("彻底重构：利用 JSON + 飞书底层 API，生成 100% 还原原版状态标签与排版的正式文档。")

uploaded_file = st.file_uploader("请上传音频或文本", type=["mp3", "wav", "m4a", "txt"])

if uploaded_file and st.button("✨ 启动原生级渲染构建", type="primary"):
    with st.status("正在执行多维处理引擎...", expanded=True) as status:
        
        # 1. 文本读取/转录
        status.write("1️⃣ 正在解析源文件...")
        if uploaded_file.name.endswith('.txt'):
            raw_text = uploaded_file.read().decode("utf-8")
        else:
            status.write("正在唤醒 Whisper 本地转录模型...")
            model = load_model()
            temp_path = f"temp_{uploaded_file.name}"
            with open(temp_path, "wb") as f: f.write(uploaded_file.getbuffer())
            raw_text = model.transcribe(temp_path, language="zh")["text"]
            os.remove(temp_path)
            
        # 2. JSON 结构化提取
        status.write("2️⃣ AI 正在进行结构化 JSON 降维解析...")
        json_data = generate_json_summary(raw_text)
        
        if json_data:
            # 3. 飞书原生 Block 映射与写入
            status.write("3️⃣ 正在映射飞书原生色彩与 Block 组件...")
            doc_id = create_feishu_doc(f"智能看板：{json_data.get('title', '会议纪要')}")
            blocks = build_native_feishu_blocks(json_data)
            doc_url = push_blocks_to_feishu(doc_id, blocks)
            
            status.update(label="✅ 原生飞书文档构建完成！", state="complete")
            
            st.markdown(f"""
            <div style="background:#f0f2f5; padding:30px; border-radius:15px; text-align:center;">
                <h2 style="color:#1f2329;">✨ 结构化仪表盘已就绪</h2>
                <p style="color:#646a73;">已通过底层 API 注入原生背景色与排版标签</p>
                <a href="{doc_url}" target="_blank" style="background:#3370ff; color:white; padding:15px 40px; text-decoration:none; border-radius:8px; font-weight:bold; font-size:18px; display:inline-block; margin-top:10px;">
                    🚀 点击检阅最终成果
                </a>
            </div>
            """, unsafe_allow_html=True)
            
            with st.expander("查看底层解析 JSON"):
                st.json(json_data)
