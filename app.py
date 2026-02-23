import streamlit as st
import google.generativeai as genai
import requests
import json
import time
import os

# --- 1. 基础配置 ---
st.set_page_config(page_title="AI 智能纪要助理", page_icon="📝", layout="centered")

# 从 Streamlit Secrets 获取密钥
if "GEMINI_API_KEY" in st.secrets:
    genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
else:
    st.error("❌ 未找到 GEMINI_API_KEY，请在 Streamlit Cloud 的 Secrets 中配置。")
    st.stop()

FEISHU_WEBHOOK = st.secrets.get("FEISHU_WEBHOOK", "")

# --- 2. 核心功能函数 ---

def push_to_feishu(content, title="会议纪要"):
    """将纪要推送到飞书机器人卡片"""
    if not FEISHU_WEBHOOK:
        return False
    
    headers = {"Content-Type": "application/json"}
    payload = {
        "msg_type": "interactive",
        "card": {
            "header": {
                "title": {"tag": "plain_text", "content": f"📅 {title}"},
                "template": "blue"
            },
            "elements": [
                {
                    "tag": "div",
                    "text": {"tag": "lark_md", "content": content}
                },
                {"tag": "hr"},
                {
                    "tag": "note",
                    "elements": [{"tag": "plain_text", "content": "✅ 由 Gemini 1.5 智能生成 | 100% 还原飞书风格"}]
                }
            ]
        }
    }
    response = requests.post(FEISHU_WEBHOOK, json=payload, headers=headers)
    return response.status_code == 200

# --- 3. UI 界面设计 ---
st.title("📝 飞书级智能纪要助手")
st.markdown("上传音频或文本，Gemini 1.5 会自动为您提取关键信息并推送至飞书。")

with st.sidebar:
    st.header("⚙️ 配置参数")
    # 修复 404 错误：使用 -latest 确保指向正确的版本
    model_name = st.selectbox("选择模型", ["gemini-1.5-flash-latest", "gemini-1.5-pro-latest"])
    st.divider()
    st.info("提示：如果上传的是音频，AI 需要一点时间‘听’完它。")

uploaded_file = st.file_uploader("选择文件 (支持 mp3, wav, m4a, txt)", type=['mp3', 'wav', 'm4a', 'txt'])

# --- 4. 主逻辑 ---
if uploaded_file and st.button("🚀 开始魔法处理"):
    try:
        model = genai.GenerativeModel(model_name=model_name)
        
        # 飞书风格的强力提示词
        prompt = """
        你现在是飞书妙记(Feishu Magic Minutes)的数字孪生。请深度解析这段内容，并生成一份 100% 还原飞书风格的结构化纪要。
        
        要求格式严格遵守以下模块（使用 Markdown）：
        
        1. **【会议概览】**：用简练的段落说明会议核心背景及最终共识。
        2. **【关键词】**：提取 5 个核心标签（如 #项目进度）。
        3. **【议程回顾】**：按逻辑顺序拆解会议，每一项包含议题名称和讨论细节。
        4. **【待办事项 ✅】**：提取所有具体的任务项。格式：@负责人 任务内容 (截止日期/优先级)。
        5. **【精彩瞬间】**：摘录 1-2 句最具决策性的原话。
        """

        with st.spinner("⏳ AI 正在深度处理中，请稍候..."):
            # 区分处理音频和文本
            if uploaded_file.type.startswith("audio"):
                # 使用 Gemini File API 处理音频
                with st.status("正在上传并转录音频...", expanded=True) as status:
                    # 临时保存文件
                    with open(uploaded_file.name, "wb") as f:
                        f.write(uploaded_file.getbuffer())
                    
                    # 上传至 Google 服务器
                    gemini_file = genai.upload_file(path=uploaded_file.name)
                    
                    # 等待音频解析完成
                    while gemini_file.state.name == "PROCESSING":
                        time.sleep(3)
                        gemini_file = genai.get_file(gemini_file.name)
                    
                    status.update(label="音频解析完成！正在生成纪要...", state="complete")
                    response = model.generate_content([gemini_file, prompt])
                    # 清理本地临时文件
                    if os.path.exists(uploaded_file.name):
                        os.remove(uploaded_file.name)
            else:
                # 文本处理
                text_content = uploaded_file.read().decode("utf-8")
                response = model.generate_content([text_content, prompt])

            # 展示结果
            st.success("✨ 纪要生成成功！")
            st.markdown(response.text)
            
            # 推送飞书
            if FEISHU_WEBHOOK:
                if push_to_feishu(response.text, title=f"纪要：{uploaded_file.name}"):
                    st.info("📲 已同步至飞书机器人。")
                else:
                    st.warning("⚠️ 飞书推送失败，请检查 Webhook 地址。")
            else:
                st.warning("ℹ️ 未配置飞书 Webhook，无法同步。")

    except Exception as e:
        st.error(f"❌ 发生错误: {str(e)}")
        st.info("建议：如果是 404 错误，请尝试刷新页面或更换模型版本。")

# 页脚提示
st.divider()
st.caption("Powered by Streamlit & Google Gemini 1.5")
