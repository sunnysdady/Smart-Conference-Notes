import streamlit as st
import google.generativeai as genai
import requests
import json
import time

# --- 1. 配置与安全 ---
# 在 Streamlit Cloud 的 Settings -> Secrets 中配置以下变量
# GEMINI_API_KEY = "你的新KEY"
# FEISHU_WEBHOOK = "你的机器人Webhook"

if "GEMINI_API_KEY" in st.secrets:
    genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
else:
    st.error("请在 Secrets 中配置 GEMINI_API_KEY")

st.set_page_config(page_title="飞书级 AI 纪要", page_icon="📝")
st.title("📝 飞书级智能纪要助手")

# --- 2. 界面设计 ---
with st.sidebar:
    st.header("设置")
    model_choice = st.selectbox("选择大脑", ["gemini-1.5-flash", "gemini-1.5-pro"])
    st.info("Flash 速度快，Pro 逻辑更强（适合复杂会议）")

upload_file = st.file_uploader("上传录音或会议文稿", type=['mp3', 'wav', 'm4a', 'txt'])

# --- 3. 核心逻辑：飞书风格 Prompt ---
FEISHU_PROMPT = """
你现在是飞书妙记(Feishu Magic Minutes)的数字孪生。请深度解析这段内容，并生成一份 100% 还原飞书风格的结构化纪要。
要求输出格式严格遵守以下模块：

1. **【会议概览】**：用 200 字以内的精炼段落，说明会议背景、核心讨论点及最终达成的最高共识。
2. **【关键词】**：提取 5-8 个核心标签，如 #项目进度 #财务审核。
3. **【议程回顾】**：按逻辑顺序拆解会议，每一项需包含：
   - 议题名称：简短有力的标题
   - 核心细节：该议题下的讨论重点（用 bullet points）
4. **【待办事项 ✅】**：提取所有具体的任务项。格式：@负责人 任务内容 (截止日期/优先级)。若无明确负责人，请标注为“未分配”。
5. **【精彩瞬间】**：摘录 2-3 句会议中最具决策性或洞察力的原话。
"""

# --- 4. 执行流程 ---
if upload_file and st.button("开始魔法生成 ✨"):
    try:
        with st.spinner("AI 正在深度倾听/阅读中..."):
            model = genai.GenerativeModel(model_choice)
            
            # 处理不同类型的输入
            if upload_file.type.startswith("audio"):
                # 语音处理：Gemini 支持直接上传文件进行分析
                file_data = upload_file.read()
                # 这里的逻辑是先将文件通过 File API 上传（Gemini 推荐方式）
                temp_file = genai.upload_file(content=file_data, mime_type=upload_file.type)
                # 等待处理（Gemini 需要一点时间处理音频索引）
                while temp_file.state.name == "PROCESSING":
                    time.sleep(2)
                    temp_file = genai.get_file(temp_file.name)
                content_input = [temp_file, FEISHU_PROMPT]
            else:
                # 文本处理
                text_content = upload_file.read().decode("utf-8")
                content_input = [text_content, FEISHU_PROMPT]

            # 生成内容
            response = model.generate_content(content_input)
            result_text = response.text

            # 预览结果
            st.markdown("### 预览生成效果")
            st.markdown(result_text)

            # --- 5. 飞书卡片推送 ---
            if "FEISHU_WEBHOOK" in st.secrets:
                card_payload = {
                    "msg_type": "interactive",
                    "card": {
                        "header": {"title": {"tag": "plain_text", "content": "🤖 会议纪要自动送达"}, "template": "blue"},
                        "elements": [
                            {"tag": "div", "text": {"tag": "lark_md", "content": result_text}},
                            {"tag": "hr"},
                            {"tag": "note", "elements": [{"tag": "plain_text", "content": f"由 {model_choice} 生成 | 来源：你的工具网站"}]}
                        ]
                    }
                }
                requests.post(st.secrets["FEISHU_WEBHOOK"], json=card_payload)
                st.success("✅ 纪要已同步至飞书机器人！")
            else:
                st.warning("未配置飞书 Webhook，仅在网页预览。")

    except Exception as e:
        st.error(f"发生错误: {str(e)}")