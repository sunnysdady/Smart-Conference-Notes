import streamlit as st
import google.generativeai as genai
import requests
import json
import time
import os

# --- 1. 基础页面配置 ---
st.set_page_config(page_title="飞书级 AI 纪要助手", page_icon="📝", layout="centered")

# 从 Streamlit Secrets 安全获取密钥 [不要把 Key 直接写在代码里]
if "GEMINI_API_KEY" in st.secrets:
    genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
else:
    st.error("❌ 未找到 GEMINI_API_KEY。请在 Streamlit Cloud 的 Settings -> Secrets 中配置。")
    st.stop()

FEISHU_WEBHOOK = st.secrets.get("FEISHU_WEBHOOK", "")

# --- 2. 飞书卡片推送函数 ---
def push_to_feishu(content, file_name):
    if not FEISHU_WEBHOOK:
        return False
    
    headers = {"Content-Type": "application/json"}
    # 构造飞书交互式卡片
    payload = {
        "msg_type": "interactive",
        "card": {
            "header": {
                "title": {"tag": "plain_text", "content": "🤖 智能会议纪要已生成"},
                "template": "blue"
            },
            "elements": [
                {"tag": "div", "text": {"tag": "lark_md", "content": f"**📁 文件名称：** {file_name}"}},
                {"tag": "hr"},
                {"tag": "div", "text": {"tag": "lark_md", "content": content}},
                {"tag": "hr"},
                {"tag": "note", "elements": [{"tag": "plain_text", "content": "由 Gemini 1.5 强力驱动 | 还原飞书妙记风格"}]}
            ]
        }
    }
    try:
        response = requests.post(FEISHU_WEBHOOK, json=payload, headers=headers)
        return response.status_code == 200
    except:
        return False

# --- 3. UI 界面设计 ---
st.title("📝 飞书级智能纪要助手")
st.markdown("上传音频或文本，AI 会自动为您生成结构化纪要并同步至飞书。")

with st.sidebar:
    st.header("⚙️ 配置")
    # 采用 -latest 后缀规避 404 错误
    model_choice = st.selectbox("选择大脑", ["gemini-1.5-flash-latest", "gemini-1.5-pro-latest"])
    st.info("提示：音频文件越大，处理时间越长（通常为音频长度的 1/5）。")

uploaded_file = st.file_uploader("支持 mp3, wav, m4a, txt", type=['mp3', 'wav', 'm4a', 'txt'])

# --- 4. 核心提示词 (飞书风格灵魂) ---
FEISHU_PROMPT = """
你现在是飞书妙记(Feishu Magic Minutes)的数字孪生。请深度解析内容，生成一份 100% 还原飞书风格的结构化纪要。
输出格式要求：
1. **【会议概览】**：用简练语言说明背景、核心讨论点及最高共识。
2. **【关键词】**：提取 5 个核心标签（如 #项目进度）。
3. **【议程回顾】**：按逻辑顺序拆解会议，包含议题名称和详细讨论点。
4. **【待办事项 ✅】**：提取任务。格式：@负责人 任务内容 (截止日期/优先级)。
5. **【精彩瞬间】**：摘录 1-2 句最具决策性的原话。
"""

# --- 5. 处理流程 ---
if uploaded_file and st.button("🚀 开始魔法处理"):
    try:
        model = genai.GenerativeModel(model_name=model_choice)
        
        with st.spinner("⏳ AI 正在深度处理中..."):
            # 区分处理音频和文本
            if uploaded_file.type.startswith("audio"):
                # 1. 临时保存音频
                with open(uploaded_file.name, "wb") as f:
                    f.write(uploaded_file.getbuffer())
                
                # 2. 上传至 Gemini File API (Gemini 直接听音频效果最好)
                gemini_file = genai.upload_file(path=uploaded_file.name)
                
                # 3. 等待处理
                while gemini_file.state.name == "PROCESSING":
                    time.sleep(3)
                    gemini_file = genai.get_file(gemini_file.name)
                
                # 4. 生成纪要
                response = model.generate_content([gemini_file, FEISHU_PROMPT])
                
                # 清理临时文件
                os.remove(uploaded_file.name)
            else:
                # 纯文本处理
                text_content = uploaded_file.read().decode("utf-8")
                response = model.generate_content([text_content, FEISHU_PROMPT])

            # 预览结果
            st.success("✨ 纪要生成成功！")
            st.markdown(response.text)
            
            # 回传飞书
            if push_to_feishu(response.text, uploaded_file.name):
                st.info("📲 已同步至飞书机器人。")
            else:
                st.warning("⚠️ 推送飞书失败，请检查 Webhook 配置。")

    except Exception as e:
        st.error(f"❌ 运行出错: {str(e)}")
