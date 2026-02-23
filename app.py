import streamlit as st
import requests
import json
import os
import time
import whisper

# ===================== 1. 基础配置 =====================
st.set_page_config(page_title="飞书级智能纪要-通义版", page_icon="📝", layout="wide")

# 填入你指定的通义千问 Key
QWEN_API_KEY = "sk-ecb46034c430477e9c9a4b4fd6589742"
FEISHU_WEBHOOK = st.secrets.get("FEISHU_WEBHOOK", "")

@st.cache_resource
def load_whisper_model():
    return whisper.load_model("base")

whisper_model = load_whisper_model()

# ===================== 2. 格式化与过滤逻辑 (还原灵魂) =====================

def fix_feishu_format(summary):
    """
    1:1 复刻飞书智能纪要排版规则
    """
    # 标题居中与加粗处理
    summary = summary.replace("## 会议主题", "<h2 style='text-align:center; font-weight:bold;'>会议主题</h2>")
    summary = summary.replace("## 决策结论", "## **决策结论**")
    # 修正待办事项的飞书特有编号感
    for i in range(1, 10):
        summary = summary.replace(f"- 待办事项：{i}.", f"{i}. 待办事项：")
    return summary

def clean_transcript(text):
    """
    过滤语气词，提升 AI 总结精度
    """
    filler_words = ["嗯", "啊", "这个", "那个", "然后", "其实", "就是说", "好的", "行"]
    for word in filler_words:
        text = text.replace(word, "")
    return text.strip()

# ===================== 3. 核心功能函数 =====================

def generate_qwen_summary(transcript_text):
    """
    调用通义千问，严格执行飞书模板约束
    """
    url = "https://dashscope.aliyuncs.com/api/v1/services/aigc/text-generation/generation"
    headers = {
        "Authorization": f"Bearer {QWEN_API_KEY}",
        "Content-Type": "application/json"
    }
    
    # 采用你提供的强约束 Prompt
    prompt = f"""
    你是专业的飞书（Lark）智能纪要助手，必须严格按照以下要求生成会议纪要，还原度100%：

    【输出结构】
    1. ## 会议主题：自动提炼加粗标题
    2. 参会人：识别发言人，无则标注「- 未提及」
    3. 会议时间：提取时间，无则标注「- 未提及」
    4. 核心要点总结：每条≤50字，项目符号（-），剔除重复内容
    5. ## 决策结论：加粗显示，列出所有决策点
    6. 待办事项：数字编号（1./2.），格式「动作+负责人+截止时间」

    【格式规则】
    - 语言正式简洁，和飞书官方输出一致。
    - 仅输出纪要内容，不含任何解释。

    【转写内容】
    {transcript_text}
    """

    data = {
        "model": "qwen-max",
        "input": {"messages": [{"role": "user", "content": prompt}]},
        "parameters": {"result_format": "text", "temperature": 0.1}
    }

    try:
        response = requests.post(url, headers=headers, json=data, timeout=60)
        raw_summary = response.json()["output"]["text"]
        return fix_feishu_format(raw_summary)
    except Exception as e:
        st.error(f"总结生成失败: {e}")
        return None

# ===================== 4. UI 与回传逻辑 =====================

st.title("📝 飞书级智能纪要助手 (通义版)")

uploaded_file = st.file_uploader("上传录音或文本", type=["mp3", "wav", "m4a", "txt"])

if uploaded_file and st.button("🚀 生成并回传飞书"):
    with st.spinner("⏳ 正在全力复刻飞书级纪要..."):
        # 1. 转录与预处理
        if uploaded_file.type.startswith("audio"):
            temp_path = f"temp_{uploaded_file.name}"
            with open(temp_path, "wb") as f:
                f.write(uploaded_file.getbuffer())
            result = whisper_model.transcribe(temp_path, language="zh")
            full_text = clean_transcript(result["text"])
            os.remove(temp_path)
        else:
            full_text = clean_transcript(uploaded_file.read().decode("utf-8"))
        
        # 2. 生成飞书风格纪要
        final_summary = generate_qwen_summary(full_text)
        
        if final_summary:
            # 网页显示
            st.markdown(final_summary, unsafe_allow_html=True)
            
            # 3. 飞书卡片推送 (同步还原标题与结构)
            if FEISHU_WEBHOOK:
                payload = {
                    "msg_type": "interactive",
                    "card": {
                        "header": {"title": {"tag": "plain_text", "content": "📅 智能会议纪要"}, "template": "blue"},
                        "elements": [
                            {"tag": "div", "text": {"tag": "lark_md", "content": final_summary.replace("<h2 style='text-align:center; font-weight:bold;'>", "## ").replace("</h2>", "")}},
                            {"tag": "note", "elements": [{"tag": "plain_text", "content": f"来源文件: {uploaded_file.name}"}]}
                        ]
                    }
                }
                requests.post(FEISHU_WEBHOOK, json=payload)
                st.toast("✅ 纪要已同步至飞书群！")
