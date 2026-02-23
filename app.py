import streamlit as st
import requests
import json
import os
import whisper
import time

# ===================== 1. 基础配置与视觉风格 =====================
st.set_page_config(page_title="飞书云文档纪要生成器", page_icon="📝", layout="wide")

# 飞书开放平台凭证 (已根据你提供的信息更新)
APP_ID = "cli_a916f070b0f8dcd6"
APP_SECRET = "gHOYZxXsoTXpmsnyf37C5dqcN4tOkibW"
QWEN_API_KEY = "sk-ecb46034c430477e9c9a4b4fd6589742"

# 网页端预览 CSS (保持网页端美观)
st.markdown("""
<style>
    .docx-preview { background: #ffffff; border: 1px solid #dee0e3; border-radius: 10px; padding: 25px; box-shadow: 0 4px 12px rgba(0,0,0,0.05); }
    .tag-green { color: #00b67a; font-weight: bold; }
    .tag-red { color: #f53f3f; font-weight: bold; }
</style>
""", unsafe_allow_html=True)

# ===================== 2. 飞书云文档 API 核心逻辑 =====================

def get_tenant_access_token():
    """获取飞书 API 调用凭证"""
    url = "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal"
    res = requests.post(url, json={"app_id": APP_ID, "app_secret": APP_SECRET})
    return res.json().get("tenant_access_token")

def create_feishu_document(title):
    """在飞书云空间创建一个空白文档"""
    token = get_tenant_access_token()
    url = "https://open.feishu.cn/open-apis/docx/v1/documents"
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    
    # 创建文档 (默认存放在应用对应的文件夹下)
    res = requests.post(url, headers=headers, json={"title": title})
    return res.json().get("data", {}).get("document", {}).get("document_id")

def write_content_to_doc(document_id, summary_text):
    """
    将 AI 生成的内容转换为飞书 Docx 的 Block 结构并写入
    注：此处简化逻辑，将主要段落写入，实际生产环境建议解析 Markdown 标签
    """
    token = get_tenant_access_token()
    url = f"https://open.feishu.cn/open-apis/docx/v1/documents/{document_id}/blocks/0/children"
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    
    # 构造文档块 (Blocks)
    # 飞书文档由不同的 Block 组成，如标题(3)、文本(2)、表格(31)等
    blocks = []
    lines = summary_text.split('\n')
    
    for line in lines:
        if not line.strip(): continue
        
        block_type = 2 # 默认为普通文本
        if line.startswith('###'): block_type = 3 # 映射为标题
        
        blocks.append({
            "block_type": block_type,
            "text": {
                "content": line.replace('#', '').strip(),
                "style": {}
            }
        })

    payload = {"children": blocks, "index": -1}
    requests.post(url, headers=headers, json=payload)
    return f"https://bytedance.feishu.cn/docx/{document_id}"

# ===================== 3. AI 生成与处理逻辑 =====================

@st.cache_resource
def load_whisper_model():
    return whisper.load_model("base")

def generate_pro_summary(content):
    """调用通义千问生成适配云文档结构的纪要"""
    url = "https://dashscope.aliyuncs.com/api/v1/services/aigc/text-generation/generation"
    headers = {"Authorization": f"Bearer {QWEN_API_KEY}", "Content-Type": "application/json"}
    
    prompt = f"""
    你现在是飞书官方智能秘书。请按照提供的 PDF 样例风格生成一份适合转为云文档的内容。
    必须包含以下模块：
    1. ### 会议总结与重点项目 (标注状态：正常推进/存在风险)
    2. ### 运营工作跟进 (详细列表)
    3. ### 关键决策与执行依据
    4. ### 下一步计划
    
    转录原文：{content}
    """
    
    data = {
        "model": "qwen-max",
        "input": {"messages": [{"role": "user", "content": prompt}]},
        "parameters": {"result_format": "text"}
    }
    res = requests.post(url, headers=headers, json=data)
    return res.json()["output"]["text"]

# ===================== 4. UI 界面逻辑 =====================

st.title("🚀 飞书级智能纪要：云文档一键生成")
st.info("此版本将直接在您的飞书空间创建 .docx 文档，实现完美排版。")

uploaded_file = st.file_uploader("上传录音或粘贴文本", type=["mp3", "wav", "m4a", "txt"])

if uploaded_file and st.button("✨ 生成飞书云文档", type="primary"):
    with st.spinner("🧠 正在解析语义并构建云文档 blocks..."):
        # 1. 获取转写文本 (此处简化为文本或快速转写)
        if uploaded_file.type.startswith("audio"):
            model = load_whisper_model()
            temp_path = f"temp_{uploaded_file.name}"
            with open(temp_path, "wb") as f: f.write(uploaded_file.getbuffer())
            raw_text = model.transcribe(temp_path)["text"]
            os.remove(temp_path)
        else:
            raw_text = uploaded_file.read().decode("utf-8")
        
        # 2. 生成结构化总结
        summary = generate_pro_summary(raw_text)
        
        if summary:
            # 3. 创建并写入飞书云文档
            doc_id = create_feishu_document(f"智能纪要：{uploaded_file.name}")
            doc_url = write_content_to_doc(doc_id, summary)
            
            # 4. 成功展示
            st.success(f"🎉 云文档创建成功！")
            st.balloons()
            
            # 醒目的跳转按钮
            st.markdown(f"""
            <div style="text-align: center; padding: 20px;">
                <a href="{doc_url}" target="_blank" style="background-color: #3370ff; color: white; padding: 15px 30px; text-decoration: none; border-radius: 5px; font-weight: bold;">
                    🚀 点击进入飞书云文档看板
                </a>
            </div>
            """, unsafe_allow_html=True)
            
            with st.expander("查看摘要预览"):
                st.markdown(summary)
