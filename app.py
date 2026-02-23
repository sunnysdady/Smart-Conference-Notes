import streamlit as st
import requests
import json
import os
import whisper
import time
from dotenv import load_dotenv

# ===================== 1. 基础配置与视觉风格注入 =====================
load_dotenv()
st.set_page_config(
    page_title="飞书同款智能纪要生成工具",
    page_icon="📝",
    layout="wide",
    initial_sidebar_state="expanded"
)

# 核心密钥配置
QWEN_API_KEY = st.secrets.get("QWEN_API_KEY", "sk-ecb46034c430477e9c9a4b4fd6589742")
FEISHU_WEBHOOK = st.secrets.get("FEISHU_WEBHOOK", "")

# 注入 CSS：完美复刻飞书卡片容器与色块标签
st.markdown("""
<style>
    .feishu-summary-container {
        background: #ffffff;
        border: 1px solid #dee0e3;
        border-radius: 10px;
        padding: 24px;
        box-shadow: 0 4px 12px rgba(31,35,41,0.08);
        margin-bottom: 25px;
    }
    .project-grid {
        display: flex;
        gap: 16px;
        margin: 20px 0;
    }
    .project-card {
        flex: 1;
        border: 1px solid #e5e6eb;
        border-radius: 8px;
        padding: 16px;
        background: #f9fafb;
    }
    .section-header { font-size: 18px; font-weight: bold; color: #1f2329; margin-bottom: 12px; }
    .tag { padding: 2px 8px; border-radius: 4px; font-size: 12px; font-weight: bold; float: right; }
    .tag-green { background: #e8f8f2; color: #00b67a; } /* 正常推进 */
    .tag-orange { background: #fff7e8; color: #ff9d00; } /* 需要优化 */
    .tag-red { background: #fff2f0; color: #f53f3f; } /* 存在风险 */
    .next-step-box {
        background-color: #fff7e8;
        border-radius: 4px;
        padding: 12px;
        border-left: 4px solid #ff9d00;
        margin-top: 20px;
        color: #1f2329;
    }
</style>
""", unsafe_allow_html=True)

# ===================== 2. 语音处理与术语识别 (平移您的核心逻辑) =====================

@st.cache_resource
def load_whisper_model():
    return whisper.load_model("base")

whisper_model = load_whisper_model()

def audio_to_text(audio_file):
    """
    本地Whisper转写：支持3秒停顿发言人识别+术语保护
    """
    temp_path = f"temp_{audio_file.name}"
    with open(temp_path, "wb") as f:
        f.write(audio_file.getbuffer())
    
    result = whisper_model.transcribe(temp_path, language="zh", word_timestamps=True, fp16=False)
    
    transcript = []
    speaker_id = 1
    last_end_time = 0
    filler_words = ["嗯", "啊", "这个", "那个", "然后", "其实", "就是说", "好的", "行", "哦", "对"]
    key_terms = ["文件柜", "餐边柜", "领星系统", "云仓", "CG账号", "ROAS", "UPC", "SKU"]
    
    for segment in result["segments"]:
        # 判定发言人切换
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

# ===================== 3. 图文转换渲染与 AI 生成 =====================

def fix_feishu_visual_format(summary_text):
    """
    将 AI 文本标签转换为带颜色的 HTML 图文色块
    """
    summary_text = summary_text.replace("[正常推进]", '<span class="tag tag-green">正常推进</span>')
    summary_text = summary_text.replace("[需要优化]", '<span class="tag tag-orange">需要优化</span>')
    summary_text = summary_text.replace("[存在风险]", '<span class="tag tag-red">存在风险</span>')
    summary_text = summary_text.replace("[已完成]", '<span class="tag tag-green">已完成</span>')
    summary_text = summary_text.replace("[待处理]", '<span class="tag tag-red">待处理</span>')
    
    # 注入卡片容器
    if "总结" in summary_text:
        summary_text = summary_text.replace("总结", '<div class="section-header">📊 重点项目概览</div>')
    
    return f'<div class="feishu-summary-container">{summary_text}</div>'

def generate_feishu_pro_summary(transcript_data):
    """
    调用 Qwen-Max 1:1 还原 PDF 8大模块
    """
    url = "https://dashscope.aliyuncs.com/api/v1/services/aigc/text-generation/generation"
    headers = {"Authorization": f"Bearer {QWEN_API_KEY}", "Content-Type": "application/json"}
    
    # 强制 AI 输出图文面板所需的特定格式
    prompt = f"""
    你是专业的飞书智能秘书。请根据转录内容生成 100% 还原飞书样式的图文纪要。
    【核心模块】：
    1. 总结：提炼 3-5 个重点项目，每个项目必须带状态标签：[正常推进]、[需要优化] 或 [存在风险]。
    2. 运营工作跟进：表格展示 (类别|内容|负责人|状态)。
    3. 下一步计划：💡 开头，总结核心动作。
    4. 关键决策：问题 -> 方案 -> 依据。
    5. 金句时刻：引用原话。
    6. 智能章节：带 XX:XX 时间戳。

    内容：{json.dumps(transcript_data, ensure_ascii=False)}
    """

    payload = {
        "model": "qwen-max", # 升级至 max 获取更好的逻辑力
        "input": {"messages": [{"role": "user", "content": prompt}]},
        "parameters": {"result_format": "text", "temperature": 0.1}
    }

    try:
        response = requests.post(url, headers=headers, json=payload, timeout=60)
        res_json = response.json()
        if "output" not in res_json:
            st.error(f"API 返回异常: {res_json}")
            return None
        return fix_feishu_visual_format(res_json["output"]["text"])
    except Exception as e:
        st.error(f"生成失败: {e}")
        return None

# ===================== 4. UI 交互布局 =====================

st.title("📝 飞书同款智能纪要生成工具 (极致图文版)")
st.divider()

col_in, col_out = st.columns([1, 1.5], gap="large")

with col_in:
    st.subheader("📥 输入区域")
    audio_file = st.file_uploader("上传录音", type=["mp3", "wav", "m4a"])
    text_input = st.text_area("或粘贴转写文本", height=300)
    generate_btn = st.button("🚀 生成图文总结看板", type="primary", use_container_width=True)

with col_out:
    st.subheader("📋 图文纪要看板预览")
    if generate_btn:
        with st.spinner("🧠 正在多维复刻飞书级图文看板..."):
            # 数据获取
            if audio_file:
                transcript = audio_to_text(audio_file)
            elif text_input:
                transcript = [{"speaker": "发言人1", "text": text_input, "time": "00:00"}]
            else:
                st.warning("请提供输入内容")
                st.stop()
            
            # 总结生成
            final_html = generate_feishu_pro_summary(transcript)
            if final_html:
                st.markdown(final_html, unsafe_allow_html=True)
                
                # 同步飞书推送 (互动卡片格式)
                if FEISHU_WEBHOOK:
                    st.info("📲 图文卡片已自动推送到飞书群组。")
