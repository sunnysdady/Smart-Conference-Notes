import streamlit as st
import google.generativeai as genai
import requests
import time
import os

# --- 1. 基础配置与安全 ---
st.set_page_config(page_title="AI 智能纪要助理 - 自动选型版", page_icon="🤖", layout="wide")

if "GEMINI_API_KEY" in st.secrets:
    genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
else:
    st.error("❌ 请在 Streamlit Cloud 的 Secrets 中配置 GEMINI_API_KEY")
    st.stop()

FEISHU_WEBHOOK = st.secrets.get("FEISHU_WEBHOOK", "")

# --- 2. 智能模型管理 ---

def get_available_models():
    """实时获取当前 API Key 支持的所有模型列表"""
    try:
        # 过滤出支持生成内容的模型
        models = [m.name.replace('models/', '') for m in genai.list_models() 
                 if 'generateContent' in m.supported_generation_methods]
        return models
    except Exception as e:
        st.error(f"模型列表获取失败: {e}")
        return ["gemini-1.5-flash"]

def auto_select_model(uploaded_file, available_models):
    """根据文件类型和大小自动匹配最优模型"""
    is_audio = uploaded_file.type.startswith("audio")
    file_size_kb = uploaded_file.size / 1024
    
    # 优先级定义：2.0/2.5 是目前最先进的
    if is_audio:
        # 音频任务：Flash 模型速度快且对语音索引支持极佳
        priority = ["gemini-2.0-flash", "gemini-2.5-flash", "gemini-1.5-flash"]
    elif file_size_kb > 100:
        # 大文本任务：优先使用 Pro 系列保证深度理解
        priority = ["gemini-2.0-pro", "gemini-2.5-pro", "gemini-1.5-pro"]
    else:
        # 普通任务：追求极致响应速度
        priority = ["gemini-2.0-flash", "gemini-2.0-flash-lite", "gemini-1.5-flash"]
    
    # 在可用列表中寻找匹配项
    for p in priority:
        if p in available_models:
            return p
    return available_models[0] # 保底选择

# --- 3. 飞书卡片推送 (还原飞书感) ---

def push_to_feishu(content, file_name, model_used):
    if not FEISHU_WEBHOOK: return False
    
    # 飞书蓝模板
    payload = {
        "msg_type": "interactive",
        "card": {
            "header": {
                "title": {"tag": "plain_text", "content": "📅 智能会议纪要 (Feishu Style)"},
                "template": "blue"
            },
            "elements": [
                {"tag": "div", "text": {"tag": "lark_md", "content": f"**📁 来源文件：** {file_name}\n**🧠 执行模型：** `{model_used}`"}},
                {"tag": "hr"},
                {"tag": "div", "text": {"tag": "lark_md", "content": content}},
                {"tag": "hr"},
                {
                    "tag": "note", 
                    "elements": [{"tag": "plain_text", "content": "✅ 已自动提取议程与待办事项 | 100% AI 驱动"}]
                }
            ]
        }
    }
    try:
        r = requests.post(FEISHU_WEBHOOK, json=payload, timeout=10)
        return r.status_code == 200
    except: return False

# --- 4. UI 界面 ---

st.title("📝 飞书级智能纪要助手")
st.caption("基于 Gemini 多模态模型，自动选型，一键推送到飞书。")

# 侧边栏：显示诊断信息
with st.sidebar:
    st.header("⚙️ 系统状态")
    all_models = get_available_models()
    st.write(f"当前可用模型数: {len(all_models)}")
    with st.expander("查看模型清单"):
        st.write(all_models)
    st.divider()
    st.warning("注：上传音频后请耐心等待，AI 需要时间扫描音轨。")

uploaded_file = st.file_uploader("拖入音频或会议文稿 (mp3, wav, m4a, txt)", type=['mp3', 'wav', 'm4a', 'txt'])

# --- 5. 核心处理逻辑 ---

if uploaded_file:
    # 自动执行选型逻辑
    target_model = auto_select_model(uploaded_file, all_models)
    st.info(f"✨ **智能选型结果**：已自动选择最优模型 `{target_model}` 来处理您的文件。")
    
    if st.button("🚀 开始魔法处理"):
        try:
            model = genai.GenerativeModel(model_name=f"models/{target_model}")
            
            # 强化 Prompt：确保 100% 还原飞书逻辑
            prompt = """
            你现在是飞书妙记(Feishu Magic Minutes)的数字孪生。请深度解析以下内容，并生成一份完美的结构化纪要。
            
            必须包含以下模块：
            1. **【会议概览】**：两句话总结核心背景与共识。
            2. **【关键词】**：5个带#号的标签。
            3. **【议程回顾】**：按逻辑顺序拆解会议讨论点（带重点详情）。
            4. **【待办事项 ✅】**：提取明确的任务、负责人和截止日期。
            5. **【精彩瞬间】**：摘录 1-2 句最具决策性的原话。
            
            请直接输出 Markdown 内容。
            """

            with st.spinner(f"正在使用 {target_model} 深度处理中..."):
                if uploaded_file.type.startswith("audio"):
                    # 处理音频：保存临时文件并上传
                    temp_name = f"temp_{int(time.time())}.{uploaded_file.name.split('.')[-1]}"
                    with open(temp_name, "wb") as f:
                        f.write(uploaded_file.getbuffer())
                    
                    gemini_file = genai.upload_file(path=temp_name)
                    while gemini_file.state.name == "PROCESSING":
                        time.sleep(2)
                        gemini_file = genai.get_file(gemini_file.name)
                    
                    response = model.generate_content([gemini_file, prompt])
                    os.remove(temp_name) # 清理
                else:
                    # 处理文本
                    text_content = uploaded_file.read().decode("utf-8")
                    response = model.generate_content([text_content, prompt])

                # 预览与推送
                st.success("🎉 生成完成！")
                st.markdown(response.text)

                if push_to_feishu(response.text, uploaded_file.name, target_model):
                    st.toast("已同步至飞书群！", icon='📲')
                else:
                    st.error("推送飞书失败，请检查 Webhook。")

        except Exception as e:
            st.error(f"发生错误: {str(e)}")
