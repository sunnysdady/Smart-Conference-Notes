import streamlit as st
import requests
import json
import os
import time
import whisper
from dotenv import load_dotenv

# ===================== 1. 基础配置与视觉风格注入 =====================
load_dotenv()
st.set_page_config(
    page_title="飞书级图文智能纪要",
    page_icon="📝",
    layout="wide",
    initial_sidebar_state="expanded"
)

# 核心密钥配置 (请确保在 Streamlit Cloud Secrets 中配置了这两个 Key)
QWEN_API_KEY = st.secrets.get("QWEN_API_KEY", "sk-ecb46034c430477e9c9a4b4fd6589742")
FEISHU_WEBHOOK = st.secrets.get("FEISHU_WEBHOOK", "")

# 注入 CSS：强制文字颜色，防止背景融合，1:1 复刻飞书看板
st.markdown("""
<style>
    /* 强制重置 Streamlit 文本颜色，防止与白色背景融合 */
    .stMarkdown, .stText, p, li, h1, h2, h3, h4, td, th {
        color: #1f2329 !important;
    }
    /* 飞书风格卡片容器 */
    .feishu-summary-box {
        background-color: #ffffff !important;
        border: 1px solid #dee0e3;
        border-radius: 10px;
        padding: 24px;
        box-shadow: 0 4px 12px rgba(31,35,41,0.08);
        margin-bottom: 25px;
        color: #1f2329 !important;
    }
    .section-header { 
        font-size: 20px; 
        font-weight: bold; 
        color: #1f2329 !important; 
        margin-bottom: 16px; 
        border-bottom: 1px solid #f2f3f5;
        padding-bottom: 10px;
    }
    /* 飞书状态标签 */
    .tag { padding: 2px 10px; border-radius: 4px; font-size: 12px; font-weight: bold; margin-left: 8px; vertical-align: middle; }
    .tag-green { background: #e8f8f2 !important; color: #00b67a !important; } /* 正常推进 */
    .tag-orange { background: #fff7e8 !important; color: #ff9d00 !important; } /* 需要优化 */
    .tag-red { background: #fff2f0 !important; color: #f53f3f !important; } /* 存在风险 */
    
    /* 表格样式复刻 */
    table { width: 100%; border-collapse: collapse; background: white; }
    th { background-color: #f5f6f7; color: #646a73 !important; font-weight: 500; text-align: left; padding: 12px; border: 1px solid #dee0e3; }
    td { padding: 12px; border: 1px solid #dee0e3; color: #1f2329 !important; }
</style>
""", unsafe_allow_html=True)

# ===================== 2. 语音处理与术语识别逻辑 (无省略平移) =====================

@st.cache_resource
def load_whisper_model():
    return whisper.load_model("base")

whisper_model = load_whisper_model()

def audio_to_text(audio_file):
    """
    音频转写：支持3秒停顿发言人切换+术语纠错
    """
    temp_path = f"temp_{audio_file.name}"
    with open(temp_path, "wb") as f:
        f.write(audio_file.getbuffer())
    
    result = whisper_model.transcribe(temp_path, language="zh", word_timestamps=True, fp16=False)
    
    transcript = []
    speaker_id = 1
    last_end_time = 0
    filler_words = ["嗯", "啊", "这个", "那个", "然后", "其实", "对", "行", "好的"]
    key_terms = ["文件柜", "餐边柜", "领星系统", "云仓", "CG账号", "ROAS", "UPC", "SKU"]
    
    for segment in result["segments"]:
        # 3秒停顿判定逻辑
        if segment["start"] - last_end_time >= 3 and len(transcript) > 0:
            speaker_id += 1
        last_end_time = segment["end"]
        
        clean_text = segment["text"]
        for word in filler_words: clean_text = clean_text.replace(word, "")
        for term in key_terms:
            if term.lower() in clean_text.lower(): clean_text = clean_text.replace(term.lower(), term)
        
        if clean_text.strip():
            transcript.append({
                "speaker": f"发言人{speaker_id}",
                "text": clean_text.strip(),
                "time": f"{int(segment['start']//60):02d}:{int(segment['start']%60):02d}"
            })
    
    os.remove(temp_path)
    return transcript

# ===================== 3. 图文转换与 8 模块生成逻辑 =====================

def fix_visual_render(text):
    """
    将 AI 标识符映射为 HTML 视觉色块
    """
    text = text.replace("[正常推进]", '<span class="tag tag-green">正常推进</span>')
    text = text.replace("[需要优化]", '<span class="tag tag-orange">需要优化</span>')
    text = text.replace("[存在风险]", '<span class="tag tag-red">存在风险</span>')
    text = text.replace("[已完成]", '<span class="tag tag-green">已完成</span>')
    
    # 标题复刻
    text = text.replace("### 总结", '<div class="section-header">📊 重点项目概览</div>')
    text = text.replace("### 运营工作跟进", '<div class="section-header">📅 运营工作跟进</div>')
    
    return f'<div class="feishu-summary-box">{text}</div>'

def generate_pro_summary(transcript_data):
    """
    调用 Qwen-Max 1:1 还原 PDF 8 大核心模块
    """
    url = "https://dashscope.aliyuncs.com/api/v1/services/aigc/text-generation/generation"
    headers = {"Authorization": f"Bearer {QWEN_API_KEY}", "Content-Type": "application/json"}
    
    prompt = f"""
你是专业的飞书（Lark）智能秘书。请根据转录内容生成 100% 还原飞书样式的图文纪要。
输出必须严格包含以下 8 大模块，不得遗漏：
1. 【基础元信息】：录音主题、录音时间、AI 免责声明。
2. 【核心总结】：包含“总结”标题、重点项目（带 [正常推进/需要优化/存在风险] 状态标签）。
3. 【运营工作跟进】：四列表格展示 (工作类别|具体内容|负责人|状态)。
4. 【详细内容】：◦ 章节主题 -> ▪ 子项 嵌套。
5. 【下一步计划】：💡 图标开头。
6. 【待办】：数字编号指令。
7. 【智能章节】：带 XX:XX 时间戳。
8. 【关键决策+金句】：引用原话。

转录原文：{json.dumps(transcript_data, ensure_ascii=False)}
"""
    payload = {
        "model": "qwen-max",
        "input": {"messages": [{"role": "user", "content": prompt}]},
        "parameters": {"result_format": "text", "temperature": 0.1, "max_output_tokens": 4096}
    }

    try:
        response = requests.post(url, headers=headers, json=payload, timeout=90)
        res_json = response.json()
        raw_text = res_json["output"]["text"]
        return raw_text
    except Exception as e:
        st.error(f"AI 生成失败: {e}")
        return None

def push_to_feishu_card(summary_text):
    """
    构造并发送飞书互动卡片
    """
    if not FEISHU_WEBHOOK:
        return "未配置 Webhook"
    
    # 清理 HTML 标签并转换状态表情
    clean_md = summary_text.replace("[正常推进]", "🟢 **正常推进**").replace("[存在风险]", "🔴 **存在风险**")
    clean_md = clean_md.replace("[需要优化]", "🟠 **需要优化**")

    payload = {
        "msg_type": "interactive",
        "card": {
            "config": {"wide_screen_mode": True},
            "header": {
                "title": {"tag": "plain_text", "content": "📅 飞书智能会议纪要"},
                "template": "blue"
            },
            "elements": [
                {"tag": "div", "text": {"tag": "lark_md", "content": clean_md}},
                {"tag": "hr"},
                {"tag": "note", "elements": [{"tag": "plain_text", "content": "由通义千问 Qwen-Max 极致还原生成"}]}
            ]
        }
    }
    try:
        r = requests.post(FEISHU_WEBHOOK, json=payload, timeout=10)
        return "推送成功" if r.status_code == 200 else f"推送失败: {r.text}"
    except Exception as e:
        return f"网络错误: {e}"

# ===================== 4. UI 界面布局 =====================

st.title("📝 飞书级智能纪要助手 (极致图文版)")

col_left, col_right = st.columns([1, 1.5], gap="large")

with col_left:
    st.subheader("📥 输入源")
    audio_file = st.file_uploader("上传录音", type=["mp3", "wav", "m4a"])
    text_input = st.text_area("或粘贴文本", height=300, placeholder="粘贴转录文字...")
    generate_btn = st.button("🚀 生成并同步飞书", type="primary", use_container_width=True)

with col_right:
    st.subheader("📋 图文纪要看板")
    if generate_btn:
        with st.spinner("🧠 正在深度复刻飞书级图文纪要..."):
            # 获取数据
            if audio_file:
                transcript = audio_to_text(audio_file)
            elif text_input:
                transcript = [{"speaker": "发言人1", "text": text_input, "time": "00:00"}]
            else:
                st.warning("请输入会议内容")
                st.stop()
            
            # 生成纪要
            raw_summary = generate_pro_summary(transcript)
            
            if raw_summary:
                # 网页展示 (HTML 渲染)
                st.markdown(fix_visual_render(raw_summary), unsafe_allow_html=True)
                
                # 飞书同步
                status = push_to_feishu_card(raw_summary)
                st.sidebar.success(f"飞书同步状态: {status}")
                if "推送成功" in status:
                    st.toast("✅ 已成功发送至飞书！", icon="📲")
                else:
                    st.sidebar.error(status)
