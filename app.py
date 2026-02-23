import streamlit as st
import requests
import json
import os
import whisper
import time

# ===================== 1. 基础配置与状态初始化 =====================
st.set_page_config(page_title="飞书智能纪要-全功能专业版", page_icon="📝", layout="wide")

# 初始化历史记录
if "history" not in st.session_state:
    st.session_state.history = []

# 凭证配置
APP_ID = "cli_a916f070b0f8dcd6"
APP_SECRET = "gHOYZxXsoTXpmsnyf37C5dqcN4tOkibW"
QWEN_API_KEY = "sk-ecb46034c430477e9c9a4b4fd6589742"

# ===================== 2. 飞书 Docx API 封装 =====================

def get_token():
    url = "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal"
    res = requests.post(url, json={"app_id": APP_ID, "app_secret": APP_SECRET})
    return res.json().get("tenant_access_token")

def create_doc(title):
    token = get_token()
    url = "https://open.feishu.cn/open-apis/docx/v1/documents"
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    res = requests.post(url, headers=headers, json={"title": title})
    return res.json().get("data", {}).get("document", {}).get("document_id")

def write_blocks(doc_id, summary_text):
    token = get_token()
    url = f"https://open.feishu.cn/open-apis/docx/v1/documents/{doc_id}/blocks/0/children"
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    
    blocks = []
    lines = summary_text.split('\n')
    for line in lines:
        line = line.strip()
        if not line: continue
        b_type = 3 if line.startswith('###') else 2
        blocks.append({
            "block_type": b_type,
            "heading1" if b_type == 3 else "text": {
                "elements": [{"text_run": {"content": line.replace('###','').strip()}}]
            }
        })
    requests.post(url, headers=headers, json={"children": blocks[:50], "index": -1})
    return f"https://bytedance.feishu.cn/docx/{doc_id}"

# ===================== 3. 核心执行逻辑 =====================

@st.cache_resource
def load_model():
    return whisper.load_model("base")

# ===================== 4. UI 界面设计 =====================

# 侧边栏：历史任务记录
with st.sidebar:
    st.title("📚 历史任务记录")
    if not st.session_state.history:
        st.write("暂无记录")
    else:
        for item in reversed(st.session_state.history):
            st.markdown(f"**[{item['time']}]**")
            st.markdown(f"📄 [{item['name']}]({item['url']})")
            st.divider()

# 主界面
st.title("🚀 飞书级智能纪要：全格式云端还原")
st.caption("支持音频 (MP3/WAV/M4A) 或文本 (TXT) 一键转为飞书云文档看板")

uploaded_file = st.file_uploader("选择文件", type=["mp3", "wav", "m4a", "txt"])

if uploaded_file and st.button("✨ 开始处理并创建云文档", type="primary"):
    start_time = time.strftime("%H:%M:%S", time.localtime())
    
    # 使用 st.status 提供可视化的任务进度
    with st.status("正在全力处理您的文件...", expanded=True) as status:
        
        # 步骤 1: 解析/转录
        status.write("🔍 步骤 1: 正在解析文件内容...")
        if uploaded_file.type.startswith("audio") or uploaded_file.name.endswith(('.mp3', '.wav', '.m4a')):
            status.write("正在加载语音模型（首次运行可能较慢）...")
            model = load_model()
            temp_path = f"temp_{uploaded_file.name}"
            with open(temp_path, "wb") as f:
                f.write(uploaded_file.getbuffer())
            status.write("正在识别语音内容（转写中）...")
            result = model.transcribe(temp_path, language="zh")
            content = result["text"]
            os.remove(temp_path)
        else:
            content = uploaded_file.read().decode("utf-8")
        
        # 步骤 2: AI 深度总结
        if content and len(content.strip()) > 5:
            status.write("🧠 步骤 2: 通义千问正在深度复刻 8 大核心模块...")
            headers = {"Authorization": f"Bearer {QWEN_API_KEY}", "Content-Type": "application/json"}
            prompt = f"你现在是飞书秘书。请根据以下内容生成 100% 还原飞书风格的 8 大模块纪要。原文：{content[:30000]}"
            payload = {"model": "qwen-max", "input": {"messages": [{"role": "user", "content": prompt}]}, "parameters": {"result_format": "text"}}
            
            res = requests.post("https://dashscope.aliyuncs.com/api/v1/services/aigc/text-generation/generation", 
                                headers=headers, json=payload, timeout=90)
            res_data = res.json()
            
            if "output" in res_data:
                summary = res_data["output"]["text"]
                
                # 步骤 3: 写入飞书
                status.write("📄 步骤 3: 正在您的飞书空间创建云文档...")
                doc_id = create_doc(f"智能看板：{uploaded_file.name}")
                if doc_id:
                    doc_url = write_blocks(doc_id, summary)
                    
                    # 记录到历史
                    st.session_state.history.append({
                        "name": uploaded_file.name,
                        "url": doc_url,
                        "time": start_time
                    })
                    
                    status.update(label="✅ 处理完成！已为您生成云文档", state="complete", expanded=False)
                    
                    # 显示大按钮和预览
                    st.success("🎉 飞书云文档看板已生成！")
                    st.markdown(f'<a href="{doc_url}" target="_blank" style="background:#3370ff;color:white;padding:15px 40px;text-decoration:none;border-radius:8px;font-weight:bold;display:inline-block;margin-top:10px;">🚀 立即进入云文档看板</a>', unsafe_allow_html=True)
                    with st.expander("点击查看摘要预览"):
                        st.markdown(summary)
                else:
                    status.update(label="❌ 飞书文档创建失败，请检查 API 权限", state="error")
            else:
                status.update(label=f"❌ AI 生成异常: {res_data.get('message')}", state="error")
        else:
            status.update(label="❌ 处理失败：文件内容为空或太短", state="error")

st.divider()
st.caption("💡 提示：如果您上传的是长音频，转写可能需要较长时间，请耐心等待状态更新。")
