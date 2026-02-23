import streamlit as st
import google.generativeai as genai
import requests
import time
import os

# --- 1. 基础配置与安全检查 ---
st.set_page_config(page_title="飞书级智能纪要助理", page_icon="📝", layout="wide")

# 从 Secrets 获取 Key
if "GEMINI_API_KEY" in st.secrets:
    genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
else:
    st.error("❌ 未在 Streamlit Secrets 中检测到 GEMINI_API_KEY")
    st.stop()

FEISHU_WEBHOOK = st.secrets.get("FEISHU_WEBHOOK", "")

# --- 2. 核心逻辑：智能模型管理 ---

def get_available_models():
    """实时获取当前 API Key 支持的可用模型列表"""
    try:
        # 过滤出支持生成内容的模型
        models = [m.name.replace('models/', '') for m in genai.list_models() 
                 if 'generateContent' in m.supported_generation_methods]
        return models
    except Exception as e:
        # 若获取失败（通常是 429），提供保底选项
        return ["gemini-2.0-flash", "gemini-1.5-flash", "gemini-1.5-pro"]

def auto_select_model(uploaded_file, available_models):
    """根据文件特征自动决策最优模型 (针对 Pro 用户优化)"""
    is_audio = uploaded_file.type.startswith("audio")
    file_size_kb = uploaded_file.size / 1024
    
    # 优先级：优先使用 2.0 系列（响应最快、理解最强）
    if is_audio:
        # 音频任务：Flash 2.0 的音轨索引能力极强
        priority = ["gemini-2.0-flash", "gemini-1.5-flash"]
    elif file_size_kb > 200:
        # 超长文本：优先使用 Pro 或最新的实验性型号
        priority = ["gemini-2.0-pro-exp-02-05", "gemini-2.0-flash", "gemini-1.5-pro"]
    else:
        # 普通任务
        priority = ["gemini-2.0-flash", "gemini-1.5-flash"]
    
    for p in priority:
        if p in available_models: return p
    return available_models[0]

# --- 3. 飞书卡片推送 (100% 还原飞书蓝) ---

def push_to_feishu(content, file_name, model_used):
    if not FEISHU_WEBHOOK: return False
    
    payload = {
        "msg_type": "interactive",
        "card": {
            "header": {
                "title": {"tag": "plain_text", "content": "🤖 智能会议纪要已生成"},
                "template": "blue" # 飞书妙记经典蓝
            },
            "elements": [
                {"tag": "div", "text": {"tag": "lark_md", "content": f"**📁 来源文件：** {file_name}\n**🧠 处理模型：** `{model_used}`"}},
                {"tag": "hr"},
                {"tag": "div", "text": {"tag": "lark_md", "content": content}},
                {"tag": "hr"},
                {
                    "tag": "note", 
                    "elements": [{"tag": "plain_text", "content": "✨ 100% 还原飞书妙记风格 | Google AI Pro 驱动"}]
                }
            ]
        }
    }
    try:
        r = requests.post(FEISHU_WEBHOOK, json=payload, timeout=15)
        return r.status_code == 200
    except: return False

# --- 4. 主 UI 界面 ---

st.title("📝 飞书级智能纪要助手")
st.caption("上传录音或文本，自动生成结构化纪要并回传飞书机器人。")

with st.sidebar:
    st.header("⚙️ 诊断与设置")
    all_models = get_available_models()
    st.success(f"当前可用模型数: {len(all_models)}")
    st.divider()
    st.info("💡 **Pro 用户提示**：\nAPI 的免费额度限制为每分钟约 2-15 次请求。若报错 429，请稍等 1 分钟再试。")

uploaded_file = st.file_uploader("拖入文件 (mp3, wav, m4a, txt)", type=['mp3', 'wav', 'm4a', 'txt'])

if uploaded_file:
    # 自动执行智能选型
    best_model = auto_select_model(uploaded_file, all_models)
    st.info(f"🎯 **智能决策**：已为您匹配当前最佳模型 `{best_model}`")

    if st.button("🚀 开始生成并回传飞书"):
        try:
            model = genai.GenerativeModel(model_name=f"models/{best_model}")
            
            # 飞书级 Prompt 灵魂（深度还原）
            prompt = """
            你现在是飞书妙记(Feishu Magic Minutes)的数字孪生。请为我生成一份完美的结构化纪要。
            要求：
            1. **【会议概览】**：精炼说明会议背景、讨论核心及最终共识。
            2. **【关键词】**：提取5个带#号的标签。
            3. **【议程回顾】**：按逻辑拆解议题，使用列表展示讨论详情。
            4. **【待办事项 ✅】**：提取任务、负责人、截止日期。若无负责人请注为“待跟进”。
            5. **【精彩瞬间】**：摘录 1-2 句最具决策性的原话。
            直接输出 Markdown 格式。
            """

            with st.spinner(f"AI 正在深度倾听/阅读中..."):
                if uploaded_file.type.startswith("audio"):
                    # 临时保存音频
                    temp_path = f"temp_{int(time.time())}_{uploaded_file.name}"
                    with open(temp_path, "wb") as f:
                        f.write(uploaded_file.getbuffer())
                    
                    # 上传至 Gemini File API
                    g_file = genai.upload_file(path=temp_path)
                    while g_file.state.name == "PROCESSING":
                        time.sleep(3)
                        g_file = genai.get_file(g_file.name)
                    
                    response = model.generate_content([g_file, prompt])
                    os.remove(temp_path) # 清理本地空间
                else:
                    # 纯文本处理
                    text_content = uploaded_file.read().decode("utf-8")
                    response = model.generate_content([text_content, prompt])

                # 页面展示
                st.success("🎉 纪要生成成功！")
                st.markdown(response.text)

                # 自动执行推送
                if push_to_feishu(response.text, uploaded_file.name, best_model):
                    st.toast("已同步至飞书机器人卡片！", icon="📲")
                else:
                    st.warning("⚠️ 推送失败。请确认飞书 Webhook 里的关键词是否包含‘会议’或‘纪要’。")

        except Exception as e:
            if "429" in str(e):
                st.error("🚨 **触发频率限制 (Error 429)**：免费版 API 跑太快啦！请等待 60 秒后重试。")
                st.info("💡 既然您已订阅 Google AI Pro，也可以直接将文件丢进 Gemini Advanced 网页版，那里是无限制的。")
            else:
                st.error(f"❌ 运行中出错: {str(e)}")

# 页脚
st.divider()
st.caption("Powered by Gemini 2.0/2.5 & Streamlit")
