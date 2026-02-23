import streamlit as st
import google.generativeai as genai
import requests
import time
import os

# --- 1. 页面配置 ---
st.set_page_config(page_title="飞书级智能纪要助手", page_icon="📝")

# 从 Secrets 获取 Key
if "GEMINI_API_KEY" in st.secrets:
    genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
else:
    st.error("❌ 请在 Streamlit Secrets 中配置 GEMINI_API_KEY")
    st.stop()

FEISHU_WEBHOOK = st.secrets.get("FEISHU_WEBHOOK", "")

# --- 2. 诊断功能：获取当前 Key 真正支持的模型 ---
def get_available_models():
    try:
        # 只列出支持生成内容的模型
        models = [m.name.replace('models/', '') for m in genai.list_models() 
                 if 'generateContent' in m.supported_generation_methods]
        # 优先把 1.5 放在前面
        models.sort(key=lambda x: "1.5" in x, reverse=True)
        return models
    except Exception as e:
        st.error(f"获取模型列表失败: {e}")
        return ["gemini-1.5-flash", "gemini-1.5-pro"]

# --- 3. UI 界面 ---
st.title("📝 飞书级智能纪要助手")

with st.sidebar:
    st.header("⚙️ 配置参数")
    # 动态获取模型列表，防止写死名称导致 404
    available_models = get_available_models()
    model_choice = st.selectbox("选择大脑 (已过滤可用型号)", available_models)
    st.write(f"当前运行路径: {os.getcwd()}")

uploaded_file = st.file_uploader("上传录音或文本", type=['mp3', 'wav', 'm4a', 'txt'])

# --- 4. 飞书卡片函数 ---
def push_to_feishu(content, title):
    if not FEISHU_WEBHOOK: return False
    payload = {
        "msg_type": "interactive",
        "card": {
            "header": {"title": {"tag": "plain_text", "content": title}, "template": "blue"},
            "elements": [{"tag": "div", "text": {"tag": "lark_md", "content": content}}]
        }
    }
    try:
        r = requests.post(FEISHU_WEBHOOK, json=payload, timeout=10)
        return r.status_code == 200
    except: return False

# --- 5. 执行逻辑 ---
if uploaded_file and st.button("🚀 开始处理"):
    try:
        # 使用 models/ 前缀强制指定路径
        model = genai.GenerativeModel(model_name=f"models/{model_choice}")
        
        prompt = """
        你现在是飞书妙记的智能助理。请为我生成结构化纪要。
        包含：【会议概览】、【关键词】、【议程回顾】、【待办事项 ✅】、【精彩瞬间】。
        请使用 Markdown 格式。
        """

        with st.spinner(f"正在使用 {model_choice} 处理..."):
            if uploaded_file.type.startswith("audio"):
                # 音频处理
                with open("temp_audio", "wb") as f:
                    f.write(uploaded_file.getbuffer())
                gemini_file = genai.upload_file(path="temp_audio")
                while gemini_file.state.name == "PROCESSING":
                    time.sleep(2)
                    gemini_file = genai.get_file(gemini_file.name)
                response = model.generate_content([gemini_file, prompt])
                os.remove("temp_audio")
            else:
                # 文本处理
                text = uploaded_file.read().decode("utf-8")
                response = model.generate_content([text, prompt])

            st.success("✨ 生成成功！")
            st.markdown(response.text)

            if push_to_feishu(response.text, f"智能纪要: {uploaded_file.name}"):
                st.info("📲 已同步至飞书群")

    except Exception as e:
        st.error(f"❌ 运行出错: {str(e)}")
        if "404" in str(e):
            st.warning("⚠️ 依然报 404？请尝试在左侧下拉菜单中选择不带 '-latest' 的版本。")
