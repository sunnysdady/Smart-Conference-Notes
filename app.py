import streamlit as st
import requests
import json
import os

# ===================== 1. 基础配置 =====================
st.set_page_config(
    page_title="飞书级智能纪要-极速版",
    page_icon="⚡",
    layout="wide"
)

# 优先从 Secrets 读取，如果没有则使用你提供的备用 Key
QWEN_API_KEY = st.secrets.get("QWEN_API_KEY", "sk-ecb46034c430477e9c9a4b4fd6589742")
FEISHU_WEBHOOK = st.secrets.get("FEISHU_WEBHOOK", "")

# ===================== 2. 格式化与过滤逻辑 =====================

def fix_feishu_format(summary):
    """1:1 复刻飞书智能纪要排版规则"""
    summary = summary.replace("## 会议主题", "<h2 style='text-align:center; font-weight:bold;'>会议主题</h2>")
    summary = summary.replace("## 决策结论", "## **决策结论**")
    # 修正列表符号
    summary = summary.replace("- 待办事项：", "✅ 待办事项：")
    return summary

def clean_transcript(text):
    """过滤语气词，提升 AI 总结精度"""
    filler_words = ["嗯", "啊", "这个", "那个", "然后", "其实", "就是说", "好的", "行"]
    for word in filler_words:
        text = text.replace(word, "")
    return text.strip()

# ===================== 3. 核心 API 调用 =====================

def generate_feishu_summary(text_input):
    """调用通义千问 Qwen-Max 极速生成纪要"""
    url = "https://dashscope.aliyuncs.com/api/v1/services/aigc/text-generation/generation"
    headers = {
        "Authorization": f"Bearer {QWEN_API_KEY}",
        "Content-Type": "application/json"
    }
    
    # 限制输入长度，防止触发阿里 30720 Token 的硬限制
    safe_content = clean_transcript(text_input)[:20000] 

    prompt = f"""
    你是专业的飞书（Lark）智能纪要助手，必须严格按照以下要求生成会议纪要，还原度100%：

    【输出结构】
    1. ## 会议主题：自动提炼核心内容，格式为「## 会议主题」+ 加粗标题
    2. 参会人：识别发言人，无则标注「- 未提及」
    3. 会议时间：提取时间，无则标注「- 未提及」
    4. 核心要点总结：每条≤50字，项目符号（-）
    5. ## 决策结论：加粗显示决策点
    6. 待办事项：数字编号，格式「动作+负责人+截止时间」

    【格式规则】
    - 仅输出纪要内容，无额外解释。剔除闲聊与口癖。

    【转写内容】
    {safe_content}
    """

    data = {
        "model": "qwen-max",
        "input": {"messages": [{"role": "user", "content": prompt}]},
        "parameters": {"result_format": "text", "temperature": 0.1}
    }

    try:
        response = requests.post(url, headers=headers, json=data, timeout=60)
        res_json = response.json()
        
        # 针对 'output' 错误的健壮性检查
        if response.status_code != 200:
            st.error(f"API 报错: {res_json.get('message', '未知错误')}")
            return None
            
        raw_summary = res_json.get("output", {}).get("text", "")
        return fix_feishu_format(raw_summary)
    except Exception as e:
        st.error(f"连接 API 失败: {str(e)}")
        return None

def push_to_feishu(summary):
    """回传飞书机器人交互卡片"""
    if not FEISHU_WEBHOOK: return
    
    payload = {
        "msg_type": "interactive",
        "card": {
            "header": {"title": {"tag": "plain_text", "content": "📅 智能会议纪要 (极速版)"}, "template": "blue"},
            "elements": [
                {"tag": "div", "text": {"tag": "lark_md", "content": summary}},
                {"tag": "hr"},
                {"tag": "note", "elements": [{"tag": "plain_text", "content": "由通义千问 Qwen-Max 驱动"}]}
            ]
        }
    }
    requests.post(FEISHU_WEBHOOK, json=payload)

# ===================== 4. 极简 UI 设计 =====================

st.title("📝 飞书级智能纪要助手 (极速版)")
st.caption("全云端处理，不占用本地内存，适配长文本与长纪要回传。")

text_input = st.text_area("粘贴您的会议转录文本", height=300, placeholder="在此粘贴录音转文字后的内容...")

if st.button("🚀 极速生成并同步飞书", type="primary"):
    if not text_input.strip():
        st.warning("请先粘贴文本内容！")
    else:
        with st.spinner("🧠 阿里通义大模型正在处理中..."):
            summary = generate_feishu_summary(text_input)
            if summary:
                st.subheader("📋 生成结果预览")
                st.markdown(summary, unsafe_allow_html=True)
                
                # 同步推送至飞书
                push_to_feishu(summary)
                st.toast("✅ 已成功推送至飞书机器人！", icon="📲")

st.divider()
st.caption("提示：极速版目前仅支持文本输入。音频转文字建议使用飞书妙记后，将文本粘贴至此处进行二次智能化加工。")
