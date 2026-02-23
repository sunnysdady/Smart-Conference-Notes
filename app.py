import streamlit as st
import requests
import json
import time
import os

# ===================== 1. 配置信息 =====================
st.set_page_config(page_title="飞书级智能纪要-全云端极速版", page_icon="⚡", layout="wide")

# 你的通义千问 API Key
QWEN_API_KEY = "sk-ecb46034c430477e9c9a4b4fd6589742"
# 飞书机器人 Webhook (建议依然放在 Secrets)
FEISHU_WEBHOOK = st.secrets.get("FEISHU_WEBHOOK", "")

# ===================== 2. 格式化与过滤逻辑 =====================

def fix_feishu_format(summary):
    """1:1 复刻飞书智能纪要排版规则"""
    summary = summary.replace("## 会议主题", "<h2 style='text-align:center; font-weight:bold;'>会议主题</h2>")
    summary = summary.replace("## 决策结论", "## **决策结论**")
    return summary

def clean_transcript(text):
    """过滤语气词"""
    filler_words = ["嗯", "啊", "这个", "那个", "然后", "其实", "就是说", "好的", "行"]
    for word in filler_words:
        text = text.replace(word, "")
    return text.strip()

# ===================== 3. 极速版云端 API =====================

def cloud_asr_and_summary(file):
    """
    极速版：将音频发送至阿里云进行 ASR 转写并总结
    注：为了保持代码简洁且不依赖复杂 SDK，我们使用通义千问大模型直接处理文本
    如果是音频，我们采用流式上传（支持小文件快速识别）
    """
    # 步骤 A: 如果是纯文本，直接总结
    if not file.type.startswith("audio"):
        return generate_qwen_summary(file.read().decode("utf-8"))

    # 步骤 B: 如果是音频，调用阿里云 ASR 接口 (此处简化为先转写再总结)
    # 为了 100% 成功率且不安装 ffmpeg，建议使用 DashScope 的录音文件识别
    st.info("⚡ 正在通过阿里云极速转写音频...")
    
    # [此处逻辑：由于 DashScope ASR 异步接口较复杂，
    # 极速版推荐直接使用 DashScope 的音频理解大模型 qwen-audio-turbo]
    url = "https://dashscope.aliyuncs.com/api/v1/services/aigc/multimodal-generation/generation"
    headers = {"Authorization": f"Bearer {QWEN_API_KEY}"}
    
    # 构造多模态请求（直接把音频发给大模型听）
    # 注意：此接口对文件大小有要求，建议 10MB 以内，大文件需分段
    files = {'file': file}
    data = {
        "model": "qwen-audio-turbo", # 专门听音频的模型
        "input": {
            "messages": [
                {
                    "role": "user", 
                    "content": [
                        {"audio": f"file://{file.name}"},
                        {"text": "请将这段录音转成文字，并按照飞书纪要风格总结核心要点、决策和待办。"}
                    ]
                }
            ]
        }
    }
    # 由于 requests 发送 file:// 协议较复杂，
    # 这里我们退回到最稳妥的方案：用通用 ASR 流程或先提示用户
    return "由于 Streamlit 限制，建议上传文本或 5MB 以内短音频测试。长音频请联系开启异步 ASR 模块。"

def generate_qwen_summary(transcript_text):
    """调用通义千问 Qwen-Max，增加健壮性判定"""
    url = "https://dashscope.aliyuncs.com/api/v1/services/aigc/text-generation/generation"
    headers = {
        "Authorization": f"Bearer {QWEN_API_KEY}",
        "Content-Type": "application/json"
    }
    
    prompt = f"""
    你是专业的飞书智能纪要助手，必须严格按照以下要求生成会议纪要，还原度 100%：
    【输出结构】
    1. ## 会议主题：加粗标题
    2. 核心要点总结：每条≤50字
    3. ## 决策结论：加粗显示
    4. 待办事项：数字编号，格式「动作+负责人+截止时间」
    
    【内容原文】：
    {clean_transcript(transcript_text)}
    """

    payload = {
        "model": "qwen-max",
        "input": {"messages": [{"role": "user", "content": prompt}]},
        "parameters": {"result_format": "text"}
    }

    try:
        response = requests.post(url, headers=headers, json=payload, timeout=60)
        res_json = response.json()
        
        # 核心修复：增加对 output 键的检查
        if response.status_code != 200:
            st.error(f"API 返回错误: {res_json.get('message', '未知错误')}")
            return None
            
        raw_summary = res_json.get("output", {}).get("text", "")
        if not raw_summary:
            st.warning("AI 返回内容为空，请检查输入。")
            return None
            
        return fix_feishu_format(raw_summary)
    except Exception as e:
        st.error(f"连接失败: {str(e)}")
        return None

# ===================== 4. UI 界面 =====================
st.title("📝 飞书级智能纪要助手 (极速版)")

uploaded_file = st.file_uploader("上传录音(建议<10MB)或文本文件", type=["mp3", "wav", "m4a", "txt"])

if uploaded_file and st.button("🚀 极速生成并回传"):
    with st.spinner("⚡ 正在处理..."):
        # 1. 如果是文本
        if not uploaded_file.type.startswith("audio"):
            content = uploaded_file.read().decode("utf-8")
            final_summary = generate_qwen_summary(content)
        else:
            # 音频则提示
            st.warning("音频极速版需对接异步接口，请先使用‘文本粘贴’确认总结效果。")
            final_summary = None

        # 2. 结果渲染与回传
        if final_summary:
            st.markdown(final_summary, unsafe_allow_html=True)
            if FEISHU_WEBHOOK:
                # 构造飞书卡片逻辑 (略)
                requests.post(FEISHU_WEBHOOK, json={"msg_type":"text","content":{"text":final_summary}})
                st.toast("已同步飞书！")
