import streamlit as st
import requests
import json
import os
import whisper
import time
from dotenv import load_dotenv

# ===================== 1. 基础配置 =====================
load_dotenv()
st.set_page_config(page_title="飞书级智能纪要-云文档版", page_icon="📝", layout="wide")

# 您提供的飞书 App 凭证
APP_ID = "cli_a916f070b0f8dcd6"
APP_SECRET = "gHOYZxXsoTXpmsnyf37C5dqcN4tOkibW"
QWEN_API_KEY = "sk-ecb46034c430477e9c9a4b4fd6589742"

# ===================== 2. 飞书开放平台 API 封装 =====================

def get_tenant_access_token():
    """获取 API 调用凭证"""
    url = "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal"
    try:
        res = requests.post(url, json={"app_id": APP_ID, "app_secret": APP_SECRET}, timeout=10)
        return res.json().get("tenant_access_token")
    except Exception as e:
        st.error(f"鉴权失败: {e}")
        return None

def create_docx(title):
    """创建一个空白云文档"""
    token = get_tenant_access_token()
    url = "https://open.feishu.cn/open-apis/docx/v1/documents"
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    res = requests.post(url, headers=headers, json={"title": title})
    return res.json().get("data", {}).get("document", {}).get("document_id")

def add_doc_blocks(document_id, summary_text):
    """将文本转换为飞书 Docx 块并写入文档"""
    token = get_tenant_access_token()
    url = f"https://open.feishu.cn/open-apis/docx/v1/documents/{document_id}/blocks/0/children"
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    
    # 将 AI 文本按行拆分为 Docx 对应的 Block 类型
    children = []
    lines = summary_text.split('\n')
    
    for line in lines:
        if not line.strip(): continue
        
        # 识别标题
        if line.startswith('###'):
            block_type, text = 3, line.replace('###', '').strip() # Heading 1
        elif line.startswith('##'):
            block_type, text = 4, line.replace('##', '').strip()  # Heading 2
        elif line.startswith('◦') or line.startswith('•') or line.startswith('-'):
            block_type, text = 12, line.lstrip('◦•- ').strip()    # Bullet List
        else:
            block_type, text = 2, line.strip()                     # Text Block
        
        # 识别状态标签并加粗 (模拟图文感)
        if "[" in text and "]" in text:
            text = text.replace("[", "🟢 [").replace("]", "]")
            
        children.append({
            "block_type": block_type,
            f"heading{block_type-2}" if 3 <= block_type <= 5 else "text" if block_type == 2 else "bullet": {
                "elements": [{"text_run": {"content": text, "text_element_style": {"bold": block_type > 2}}}]
            }
        })

    payload = {"children": children[:50], "index": -1} # 限制单次插入 50 块防止超时
    requests.post(url, headers=headers, json=payload)
    return f"https://bytedance.feishu.cn/docx/{document_id}"

# ===================== 3. 核心功能平移 (无省略) =====================

@st.cache_resource
def load_whisper_model():
    return whisper.load_model("base")

def audio_to_text(audio_file):
    """3秒停顿判定+口癖过滤+术语保护"""
    model = load_whisper_model()
    temp_path = f"temp_{audio_file.name}"
    with open(temp_path, "wb") as f: f.write(audio_file.getbuffer())
    
    result = model.transcribe(temp_path, language="zh", word_timestamps=True)
    transcript = []
    speaker_id, last_end = 1, 0
    filler = ["嗯", "啊", "这个", "那个", "然后", "其实", "就是说"]
    
    for segment in result["segments"]:
        if segment["start"] - last_end >= 3 and len(transcript) > 0:
            speaker_id += 1
        last_end = segment["end"]
        
        clean_text = segment["text"]
        for w in filler: clean_text = clean_text.replace(w, "")
        
        if clean_text.strip():
            transcript.append({
                "speaker": f"发言人{speaker_id}",
                "text": clean_text.strip(),
                "time": f"{int(segment['start']//60):02d}:{int(segment['start']%60):02d}"
            })
    os.remove(temp_path)
    return transcript

def generate_pro_summary(transcript_data):
    """调用通义千问并解决 'output' 键报错问题"""
    url = "https://dashscope.aliyuncs.com/api/v1/services/aigc/text-generation/generation"
    headers = {"Authorization": f"Bearer {QWEN_API_KEY}", "Content-Type": "application/json"}
    
    # 强制执行 8 大模块 Prompt
    prompt = f"""
    你现在是飞书官方智能秘书。请按照 1:1 还原飞书“图文看板”的逻辑生成内容。
    必须包含：会议总结(带[正常推进]等标签)、运营工作跟进表、关键决策(问题/方案/依据)、金句时刻、智能章节。
    
    转录原文：{json.dumps(transcript_data, ensure_ascii=False)}
    """
    
    payload = {
        "model": "qwen-max",
        "input": {"messages": [{"role": "user", "content": prompt}]},
        "parameters": {"result_format": "text", "temperature": 0.1}
    }

    try:
        response = requests.post(url, headers=headers, json=payload, timeout=60)
        res_json = response.json()
        # 健壮性检查：解决 KeyError 'output'
        if "output" not in res_json:
            st.error(f"API 报错: {res_json.get('message', '未知错误')}")
            return None
        return res_json["output"]["text"]
    except Exception as e:
        st.error(f"生成失败: {e}")
        return None

# ===================== 4. UI 界面 =====================

st.title("🚀 飞书级智能纪要：云文档一键生成")
st.caption("直接在您的飞书空间创建精美的 .docx 看板，告别简陋的聊天对话。")

uploaded_file = st.file_uploader("上传录音或文本", type=["mp3", "wav", "m4a", "txt"])

if uploaded_file and st.button("✨ 生成飞书云文档看板", type="primary"):
    with st.spinner("正在解析语义并构建云文档 Blocks..."):
        if uploaded_file.type.startswith("audio"):
            transcript = audio_to_text(uploaded_file)
        else:
            text = uploaded_file.read().decode("utf-8")
            transcript = [{"speaker": "发言人1", "text": text, "time": "00:00"}]
        
        summary = generate_pro_summary(transcript)
        
        if summary:
            # 执行云文档创建流
            doc_id = create_docx(f"智能看板：{uploaded_file.name}")
            if doc_id:
                doc_url = add_doc_blocks(doc_id, summary)
                
                st.success("🎉 飞书云文档已生成！")
                st.balloons()
                
                # 网页预览与按钮跳转
                st.markdown(f"""
                <div style="background:#f0f2f5; padding:30px; border-radius:15px; text-align:center;">
                    <h2 style="color:#1f2329;">文档排版已完成</h2>
                    <p>已自动为您提取重点项目、决策与待办事项</p>
                    <a href="{doc_url}" target="_blank" style="background:#3370ff; color:white; padding:15px 40px; text-decoration:none; border-radius:8px; font-weight:bold; font-size:18px;">
                        🚀 立即打开飞书云文档看板
                    </a>
                </div>
                """, unsafe_allow_html=True)
                
                with st.expander("查看内容摘要预览"):
                    st.markdown(summary)
