import streamlit as st
import requests
import json
import os
import whisper
import time
from dotenv import load_dotenv

# ===================== 1. 基础配置与凭证 =====================
load_dotenv()
st.set_page_config(page_title="飞书级智能纪要：全格式云端生成", page_icon="📝", layout="wide")

# 凭证配置 (确保 Secrets 中已配置)
APP_ID = "cli_a916f070b0f8dcd6"
APP_SECRET = "gHOYZxXsoTXpmsnyf37C5dqcN4tOkibW"
QWEN_API_KEY = "sk-ecb46034c430477e9c9a4b4fd6589742"

# ===================== 2. 飞书 Docx API 封装 =====================

def get_tenant_token():
    url = "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal"
    res = requests.post(url, json={"app_id": APP_ID, "app_secret": APP_SECRET})
    return res.json().get("tenant_access_token")

def create_feishu_doc(title):
    token = get_tenant_token()
    url = "https://open.feishu.cn/open-apis/docx/v1/documents"
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    res = requests.post(url, headers=headers, json={"title": title})
    return res.json().get("data", {}).get("document", {}).get("document_id")

def write_to_docx(document_id, summary_text):
    token = get_tenant_token()
    url = f"https://open.feishu.cn/open-apis/docx/v1/documents/{document_id}/blocks/0/children"
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    
    blocks = []
    lines = summary_text.split('\n')
    for line in lines:
        line = line.strip()
        if not line: continue
        
        # 视觉还原：识别标题和高亮块
        b_type = 2
        if line.startswith('###'): b_type = 3
        
        blocks.append({
            "block_type": b_type,
            "heading1" if b_type == 3 else "text": {
                "elements": [{"text_run": {"content": line.replace('###','').strip()}}]
            }
        })
    
    requests.post(url, headers=headers, json={"children": blocks[:50], "index": -1})
    return f"https://bytedance.feishu.cn/docx/{document_id}"

# ===================== 3. 核心处理逻辑 =====================

@st.cache_resource
def load_whisper():
    return whisper.load_model("base")

def process_file(uploaded_file):
    """
    自动识别文件类型：音频调用 Whisper，文本直接读取
    """
    if uploaded_file.type.startswith("audio") or uploaded_file.name.endswith(('.mp3', '.wav', '.m4a')):
        with st.status("🔊 正在进行本地语音转录（约需1-3分钟）..."):
            model = load_whisper()
            temp_path = f"temp_{uploaded_file.name}"
            with open(temp_path, "wb") as f:
                f.write(uploaded_file.getbuffer())
            
            # 转录并进行简单的口癖清理
            result = model.transcribe(temp_path, language="zh")
            os.remove(temp_path)
            return result["text"]
    else:
        # 处理 TXT 文件
        return uploaded_file.read().decode("utf-8")

def generate_ai_summary(raw_text):
    """调用通义千问，并增加输入校验防止 400 错误"""
    if not raw_text or len(raw_text.strip()) < 5:
        st.error("❌ 处理失败：读取到的文本内容太短，无法生成总结。")
        return None

    url = "https://dashscope.aliyuncs.com/api/v1/services/aigc/text-generation/generation"
    headers = {"Authorization": f"Bearer {QWEN_API_KEY}", "Content-Type": "application/json"}
    
    prompt = f"你现在是飞书秘书。请根据以下内容生成 100% 还原飞书风格的 8 大模块纪要（含总结、表格、待办、决策等）。原文：{raw_text[:30000]}"
    
    payload = {"model": "qwen-max", "input": {"messages": [{"role": "user", "content": prompt}]}, "parameters": {"result_format": "text"}}
    
    try:
        res = requests.post(url, headers=headers, json=payload, timeout=90)
        res_data = res.json()
        if "output" not in res_data:
            st.error(f"AI 生成异常：{res_data.get('message', 'API 未返回内容')}")
            return None
        return res_data["output"]["text"]
    except Exception as e:
        st.error(f"网络连接失败: {e}")
        return None

# ===================== 4. UI 界面 =====================

st.title("🚀 飞书级智能纪要：全格式云端还原")
st.info("支持上传音频（MP3/WAV/M4A）或文本文档（TXT）。")

uploaded_file = st.file_uploader("选择文件", type=["mp3", "wav", "m4a", "txt"])

if uploaded_file and st.button("✨ 一键生成飞书云文档", type="primary"):
    # 1. 解析文件
    content = process_file(uploaded_file)
    
    if content:
        # 2. AI 深度总结
        summary = generate_ai_summary(content)
        
        if summary:
            # 3. 创建云文档
            doc_id = create_feishu_doc(f"智能看板：{uploaded_file.name}")
            if doc_id:
                doc_url = write_to_docx(doc_id, summary)
                st.success("🎉 飞书云文档看板已生成！")
                st.markdown(f'<a href="{doc_url}" target="_blank" style="background:#3370ff;color:white;padding:15px 40px;text-decoration:none;border-radius:8px;font-weight:bold;">🚀 立即进入云文档看板</a>', unsafe_allow_html=True)
                with st.expander("预览摘要"):
                    st.markdown(summary)
