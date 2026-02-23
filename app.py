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
    page_title="飞书级智能纪要-极致还原版",
    page_icon="📝",
    layout="wide",
    initial_sidebar_state="expanded"
)

# 核心密钥配置
QWEN_API_KEY = "sk-ecb46034c430477e9c9a4b4fd6589742"
FEISHU_WEBHOOK = st.secrets.get("FEISHU_WEBHOOK", "")

# 注入 CSS：完美复刻飞书卡片容器、色块标签和排版
st.markdown("""
<style>
    .feishu-box {
        background-color: #ffffff;
        border: 1px solid #dee0e3;
        border-radius: 10px;
        padding: 24px;
        box-shadow: 0 4px 12px rgba(31,35,41,0.08);
        margin-bottom: 20px;
        font-family: "PingFang SC", "Microsoft YaHei", sans-serif;
    }
    .section-title { font-size: 18px; font-weight: 600; color: #1f2329; margin: 20px 0 16px 0; border-bottom: 1px solid #f2f3f5; padding-bottom: 8px; }
    .tag { padding: 2px 8px; border-radius: 4px; font-size: 12px; font-weight: bold; margin-left: 8px; vertical-align: middle; }
    .tag-green { background: #e8f8f2; color: #00b67a; } /* 正常推进 / 已完成 [cite: 10, 31] */
    .tag-orange { background: #fff7e8; color: #ff9d00; } /* 需要优化 [cite: 12] */
    .tag-red { background: #fff2f0; color: #f53f3f; } /* 存在风险 [cite: 14] */
    .tag-blue { background: #e8f3ff; color: #165dff; } /* 进行中 */
    .next-plan-box { background-color: #fff7e8; border-radius: 4px; padding: 12px; border-left: 4px solid #ff9d00; margin: 15px 0; }
</style>
""", unsafe_allow_html=True)

# ===================== 2. 核心转录与净化逻辑 =====================

@st.cache_resource
def load_whisper_model():
    return whisper.load_model("base") # 平衡速度与精度

whisper_model = load_whisper_model()

def audio_to_text(audio_file):
    """
    本地Whisper转写：优化发言人区分（3秒停顿）+术语精准识别+格式修正
    """
    temp_audio_path = f"temp_{audio_file.name}"
    with open(temp_audio_path, "wb") as f:
        f.write(audio_file.getbuffer())
    
    result = whisper_model.transcribe(
        temp_audio_path,
        language="zh",
        word_timestamps=True,
        fp16=False
    )
    
    transcript = []
    speaker_id = 1
    last_end_time = 0
    filler_words = ["嗯", "啊", "这个", "那个", "然后", "其实", "就是说", "好的", "行", "哦", "呃", "对"]
    key_terms = ["文件柜", "餐边柜", "斗柜", "鞋柜", "领星系统", "云仓", "CG账号", "ROAS", "UPC", "SKU"]
    
    for segment in result["segments"]:
        # 判定发言人切换：停顿 ≥ 3秒 [cite: 37, 49]
        if segment["start"] - last_end_time >= 3 and len(transcript) > 0:
            speaker_id += 1
        last_end_time = segment["end"]
        
        clean_text = segment["text"]
        for word in filler_words: clean_text = clean_text.replace(word, "")
        for term in key_terms:
            if term.lower() in clean_text.lower(): clean_text = clean_text.replace(term.lower(), term)
        
        # 数字格式修正
        for i, cn_num in enumerate(["一","二","三","四","五","六","七","八","九","十"]):
            clean_text = clean_text.replace(cn_num, str(i+1))
            
        if clean_text.strip():
            transcript.append({
                "speaker": f"发言人{speaker_id}",
                "text": clean_text.strip(),
                "time": f"{int(segment['start']//60):02d}:{int(segment['start']%60):02d}"
            })
    
    os.remove(temp_audio_path)
    return transcript

# ===================== 3. 飞书格式化与 AI 生成逻辑 =====================

def fix_feishu_visuals(text):
    """
    1:1 复刻飞书排版样式与色块标签
    """
    # 转换状态标签
    text = text.replace("[正常推进]", '<span class="tag tag-green">正常推进</span>')
    text = text.replace("[已完成]", '<span class="tag tag-green">已完成</span>')
    text = text.replace("[需要优化]", '<span class="tag tag-orange">需要优化</span>')
    text = text.replace("[存在风险]", '<span class="tag tag-red">存在风险</span>')
    text = text.replace("[待处理]", '<span class="tag tag-red">待处理</span>')
    text = text.replace("[计划中]", '<span class="tag tag-blue">计划中</span>')
    
    # 模块标题 HTML 化
    text = text.replace("### 总结", '<div class="section-title">📊 重点项目概览</div>')
    text = text.replace("### 运营工作跟进", '<div class="section-title">📅 运营工作跟进</div>')
    text = text.replace("### 关键决策", '<div class="section-title">🎯 关键决策</div>')
    text = text.replace("### 金句时刻", '<div class="section-title">💬 金句时刻</div>')
    text = text.replace("### 待办", '<div class="section-title">✅ 待办事项</div>')
    
    # 金句样式
    text = text.replace("「", "<i style='color:#646a73;'>「").replace("」", "」</i>")
    
    return f'<div class="feishu-box">{text}</div>'

def generate_feishu_summary(transcript_data):
    """
    调用通义千问 Qwen-Max，严格执行 8 大模块 Prompt
    """
    url = "https://dashscope.aliyuncs.com/api/v1/services/aigc/text-generation/generation"
    headers = {"Authorization": f"Bearer {QWEN_API_KEY}", "Content-Type": "application/json"}
    
    prompt = f"""
你是专业的飞书（Lark）智能纪要助手，需严格按照飞书智能纪要标准生成 8 大核心模块，还原度100%：

【模块1：基础元信息】录音主题、时间（XXXX年XX月XX日格式）、AI生成免责声明。
【模块2：核心总结】包含「总结」标题、一句话主题、重点项目（带 [正常推进/需要优化/存在风险] 状态标签）。[cite: 8, 10, 12, 14]
【模块3：运营工作跟进】用四列表格展示：工作类别 | 具体内容 | 负责人 | 状态。[cite: 31]
【模块4：详细会议内容】◦ 章节主题 -> ▪ 子主题，按问题+方案+执行要求展开。[cite: 35, 44]
【模块5：下一步计划】💡 开头，总结核心动作，分点列出模块。[cite: 32]
【模块6：待办】数字编号，纯行动指令。[cite: 98, 99]
【模块7：智能章节】XX:XX 章节主题 + 100字以内概括。[cite: 104, 105]
【模块8：关键决策+金句时刻】问题/方案/依据逻辑 + 说话人金句引用。[cite: 127, 141]

【转写原始内容】
{json.dumps(transcript_data, ensure_ascii=False)}
"""
    data = {
        "model": "qwen-max",
        "input": {"messages": [{"role": "user", "content": prompt}]},
        "parameters": {"result_format": "text", "temperature": 0.1, "max_output_tokens": 4096}
    }

    try:
        response = requests.post(url, headers=headers, json=data, timeout=60)
        result = response.json()
        return result["output"]["text"]
    except Exception as e:
        st.error(f"生成失败：{str(e)}")
        return None

def push_to_feishu_bot(summary):
    """
    发送飞书互动卡片，还原卡片视觉效果
    """
    if not FEISHU_WEBHOOK: return
    # 转换标签为飞书 Markdown 表情
    card_text = summary.replace("[正常推进]", "🟢 **正常推进**").replace("[存在风险]", "🔴 **存在风险**")
    card_text = card_text.replace("[需要优化]", "🟠 **需要优化**").replace("[已完成]", "✅ **已完成**")
    
    payload = {
        "msg_type": "interactive",
        "card": {
            "header": {"title": {"tag": "plain_text", "content": "📅 飞书智能会议纪要"}, "template": "blue"},
            "elements": [
                {"tag": "div", "text": {"tag": "lark_md", "content": card_text}},
                {"tag": "hr"},
                {"tag": "note", "elements": [{"tag": "plain_text", "content": "由通义千问 Qwen-Max 极致还原生成"}]}
            ]
        }
    }
    requests.post(FEISHU_WEBHOOK, json=payload)

# ===================== 4. UI 交互布局 =====================

st.title("📝 飞书同款智能纪要生成工具")
st.divider()

col_in, col_out = st.columns([1, 2], gap="large")

with col_in:
    st.subheader("📥 输入区域")
    audio_file = st.file_uploader("上传录音 (mp3/wav/m4a)", type=["mp3", "wav", "m4a"])
    st.markdown("---")
    text_input = st.text_area("或粘贴转写文本", height=250, placeholder="发言人1：...")
    generate_btn = st.button("🚀 生成并回传飞书", type="primary", use_container_width=True)

with col_out:
    st.subheader("📋 预览区域")
    result_area = st.empty()
    if generate_btn:
        with st.spinner("🧠 正在进行多维语义复刻..."):
            # 获取内容
            if audio_file:
                transcript = audio_to_text(audio_file)
            elif text_input:
                transcript = [{"speaker": "发言人1", "text": text_input, "time": "00:00"}]
            else:
                st.warning("请输入内容")
                st.stop()
            
            # 生成纪要
            raw_summary = generate_feishu_summary(transcript)
            if raw_summary:
                # 网页显示 HTML 增强效果
                formatted_html = fix_feishu_visuals(raw_summary)
                result_area.markdown(formatted_html, unsafe_allow_html=True)
                
                # 飞书推送
                push_to_feishu_bot(raw_summary)
                st.toast("✅ 纪要已推送至飞书机器人！", icon="📲")
