import streamlit as st
import requests
import json
import os
import time
import whisper
from dotenv import load_dotenv

# ===================== 1. 界面与视觉风格配置 =====================
load_dotenv()
st.set_page_config(
    page_title="飞书级图文智能纪要",
    page_icon="🎨",
    layout="wide",
    initial_sidebar_state="expanded"
)

# 密钥配置（建议放在 Secrets 中）
QWEN_API_KEY = "sk-ecb46034c430477e9c9a4b4fd6589742"
FEISHU_WEBHOOK = st.secrets.get("FEISHU_WEBHOOK", "")

# 注入飞书原生视觉 CSS
st.markdown("""
<style>
    /* 模拟飞书总结看板 */
    .feishu-summary-card {
        background: #ffffff;
        border: 1px solid #dee0e3;
        border-radius: 10px;
        padding: 24px;
        box-shadow: 0 4px 12px rgba(31,35,41,0.08);
        margin-bottom: 20px;
    }
    /* 项目小卡片布局 */
    .project-grid {
        display: flex;
        gap: 15px;
        margin-top: 15px;
    }
    .project-item {
        flex: 1;
        border: 1px solid #e5e6eb;
        border-radius: 8px;
        padding: 12px;
        background: #f9fafb;
    }
    /* 状态标签色块 */
    .tag { padding: 2px 8px; border-radius: 4px; font-size: 12px; font-weight: bold; float: right; }
    .tag-green { background: #e8f8f2; color: #00b67a; } /* 正常推进 / 已完成 */
    .tag-orange { background: #fff7e8; color: #ff9d00; } /* 需要优化 */
    .tag-red { background: #fff2f0; color: #f53f3f; } /* 存在风险 / 待处理 */
    
    /* 下一步计划黄色引导条 */
    .next-step-bar {
        background-color: #fff7e8;
        border-radius: 4px;
        padding: 12px;
        border-left: 4px solid #ff9d00;
        color: #1f2329;
        font-weight: 500;
        margin-top: 20px;
    }
</style>
""", unsafe_allow_html=True)

# ===================== 2. 语音处理与术语识别 (平移自您的代码) =====================

@st.cache_resource
def load_whisper_model():
    return whisper.load_model("base")

whisper_model = load_whisper_model()

def audio_to_text(audio_file):
    """音频转写逻辑"""
    temp_path = f"temp_{audio_file.name}"
    with open(temp_path, "wb") as f:
        f.write(audio_file.getbuffer())
    
    result = whisper_model.transcribe(temp_path, language="zh", word_timestamps=True)
    
    transcript = []
    speaker_id = 1
    last_end_time = 0
    filler_words = ["嗯", "啊", "这个", "那个", "然后", "其实", "就是说"]
    
    for segment in result["segments"]:
        # 3秒停顿判定发言人切换
        if segment["start"] - last_end_time >= 3 and len(transcript) > 0:
            speaker_id += 1
        last_end_time = segment["end"]
        
        clean_text = segment["text"]
        for word in filler_words: clean_text = clean_text.replace(word, "")
        
        if clean_text.strip():
            transcript.append({
                "speaker": f"发言人{speaker_id}",
                "text": clean_text.strip(),
                "time": f"{int(segment['start']//60):02d}:{int(segment['start']%60):02d}"
            })
    
    os.remove(temp_path)
    return transcript

# ===================== 3. 图文纪要生成与飞书卡片推送 =====================

def generate_pro_visual_summary(transcript_data):
    """
    调用通义千问，1:1 还原 PDF 样例中的图文模块
    """
    url = "https://dashscope.aliyuncs.com/api/v1/services/aigc/text-generation/generation"
    headers = {"Authorization": f"Bearer {QWEN_API_KEY}", "Content-Type": "application/json"}
    
    # 强制 AI 输出带状态标识的结构
    prompt = f"""
    你现在是飞书(Lark)官方智能秘书。请按照提供的 PDF 样例风格生成“图文总结面板”。
    
    【核心任务】:
    1. 提炼【重点项目】：每个项目必须标注 [正常推进]、[需要优化] 或 [存在风险]。
    2. 生成【运营工作跟进】表格：类别、内容、负责人、状态（已完成/待处理/计划中）。
    3. 提取【关键决策】：问题 -> 方案 -> 依据。
    4. 提取【金句时刻】：引用说话人的原话。
    5. 提炼【智能章节】：带 XX:XX 时间戳。

    【内容原文】:
    {json.dumps(transcript_data, ensure_ascii=False)}
    """

    data = {
        "model": "qwen-max",
        "input": {"messages": [{"role": "user", "content": prompt}]},
        "parameters": {"result_format": "text", "temperature": 0.1}
    }

    try:
        response = requests.post(url, headers=headers, json=data, timeout=60)
        return response.json()["output"]["text"]
    except Exception as e:
        st.error(f"API 报错: {e}")
        return None

def push_feishu_interactive_card(summary_text):
    """
    发送飞书互动卡片，这是实现手机端“图文感”的唯一方式
    """
    if not FEISHU_WEBHOOK: return
    
    # 将标签替换为飞书卡片表情符
    card_md = summary_text.replace("[正常推进]", "🟢 **正常推进**")
    card_md = card_md.replace("[存在风险]", "🔴 **存在风险**")
    card_md = card_md.replace("[需要优化]", "🟠 **需要优化**")

    payload = {
        "msg_type": "interactive",
        "card": {
            "config": {"wide_screen_mode": True},
            "header": {
                "title": {"tag": "plain_text", "content": "📅 智能会议图文纪要"},
                "template": "blue"
            },
            "elements": [
                {"tag": "div", "text": {"tag": "lark_md", "content": card_md}},
                {"tag": "hr"},
                {"tag": "note", "elements": [{"tag": "plain_text", "content": "100% 飞书原版风格还原"}]}
            ]
        }
    }
    requests.post(FEISHU_WEBHOOK, json=payload)

# ===================== 4. 网页端排版逻辑 =====================

def render_visual_web_card(text):
    """在网页端渲染带色块的图文面板"""
    # 转换状态标签为 HTML 颜色块
    text = text.replace("[正常推进]", '<span class="tag tag-green">正常推进</span>')
    text = text.replace("[需要优化]", '<span class="tag tag-orange">需要优化</span>')
    text = text.replace("[存在风险]", '<span class="tag tag-red">存在风险</span>')
    text = text.replace("[已完成]", '<span class="tag tag-green">已完成</span>')
    text = text.replace("[待处理]", '<span class="tag tag-red">待处理</span>')
    
    # 包装到容器中
    st.markdown(f'<div class="feishu-summary-card">{text}</div>', unsafe_allow_html=True)

# ===================== 5. 主程序 UI =====================

st.title("📝 飞书级图文智能纪要助手")

uploaded_file = st.file_uploader("上传录音或文本", type=["mp3", "wav", "m4a", "txt"])

if uploaded_file and st.button("🚀 生成图文纪要并推送", type="primary"):
    with st.spinner("🧠 正在构建飞书级图文面板..."):
        # 获取源数据
        if uploaded_file.type.startswith("audio"):
            transcript = audio_to_text(uploaded_file)
        else:
            transcript = [{"speaker": "发言人", "text": uploaded_file.read().decode("utf-8"), "time": "00:00"}]
        
        # 生成纪要
        final_summary = generate_pro_visual_summary(transcript)
        
        if final_summary:
            st.subheader("📋 预览：图文纪要看板")
            # 渲染网页版图文面板
            render_visual_web_card(final_summary)
            
            # 推送飞书卡片
            push_feishu_interactive_card(final_summary)
            st.toast("✅ 图文卡片已推送至飞书！", icon="📲")
