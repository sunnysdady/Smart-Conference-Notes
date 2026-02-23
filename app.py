import streamlit as st
import requests
import json
import os
import whisper

# ===================== 1. 基础配置与视觉注入 =====================
st.set_page_config(page_title="智能纪要看板", page_icon="📊", layout="wide")

# 配置通义千问 API Key
QWEN_API_KEY = "sk-ecb46034c430477e9c9a4b4fd6589742"

# 注入 CSS：复刻 PDF 中的色块和阴影卡片
st.markdown("""
<style>
    .visual-dashboard { background: #fcfcfd; border: 1px solid #e5e6eb; border-radius: 12px; padding: 25px; margin-bottom: 20px; }
    .card-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 15px; margin-top: 15px; }
    .project-card { background: #ffffff; border: 1px solid #dee0e3; border-top: 4px solid #3370ff; border-radius: 8px; padding: 15px; box-shadow: 0 2px 6px rgba(0,0,0,0.05); }
    .tag { padding: 2px 8px; border-radius: 4px; font-size: 12px; font-weight: bold; float: right; }
    .tag-green { background: #e8f8f2; color: #00b67a; }   /* 正常推进 [cite: 10, 15] */
    .tag-orange { background: #fff7e8; color: #ff9d00; }  /* 需要优化 [cite: 11, 16] */
    .tag-red { background: #fff2f0; color: #f53f3f; }     /* 存在风险 [cite: 13, 17] */
    .next-step-bar { background: #fff7e8; border-left: 5px solid #ff9d00; padding: 15px; border-radius: 4px; margin-top: 20px; font-weight: 500; }
</style>
""", unsafe_allow_html=True)

# ===================== 2. 核心总结与图文转换逻辑 =====================

def render_feishu_dashboard(raw_ai_text):
    """
    后处理：将 AI 输出的标识符 [正常推进] 等转换为 HTML 图文色块 [cite: 15, 16, 17]
    """
    text = raw_ai_text.replace("[正常推进]", '<span class="tag tag-green">正常推进</span>')
    text = text.replace("[需要优化]", '<span class="tag tag-orange">需要优化</span>')
    text = text.replace("[存在风险]", '<span class="tag tag-red">存在风险</span>')
    
    # 模拟看板容器逻辑
    if "### 重点项目" in text:
        text = text.replace("### 重点项目", '<h3 style="color:#1f2329;">📊 重点项目概览</h3>')
    
    return f'<div class="visual-dashboard">{text}</div>'

def generate_visual_summary(content):
    """
    核心 Prompt：强制 AI 输出用于图文转换的标识符 
    """
    url = "https://dashscope.aliyuncs.com/api/v1/services/aigc/text-generation/generation"
    headers = {"Authorization": f"Bearer {QWEN_API_KEY}", "Content-Type": "application/json"}
    
    prompt = f"""
    请根据提供的会议转录内容，生成一份具有“图文看板感”的智能纪要。
    
    【核心模块要求】：
    1. **重点项目看板**：提炼3个最核心项目，每个项目必须附带 [正常推进]、[需要优化] 或 [存在风险] 状态标签。 [cite: 8, 14]
    2. **运营工作表格**：生成 工作类别 | 具体内容 | 负责人 | 状态 的 Markdown 表格。 [cite: 31]
    3. **下一步计划**：💡 开头，总结后续核心动作。 [cite: 32]
    4. **关键决策**：用“问题->方案->依据”结构提炼决策点。 [cite: 128-133]
    5. **待办清单**：数字编号，列出具体的行动指令。 [cite: 98-101]

    【原文内容】：
    {content}
    """
    
    data = {
        "model": "qwen-max",
        "input": {"messages": [{"role": "user", "content": prompt}]},
        "parameters": {"result_format": "text", "temperature": 0.2}
    }
    
    try:
        response = requests.post(url, headers=headers, json=data, timeout=60)
        raw_text = response.json()["output"]["text"]
        return render_feishu_dashboard(raw_text)
    except Exception as e:
        st.error(f"生成失败: {e}")
        return None

# ===================== 3. UI 布局界面 =====================

st.title("📑 智能纪要可视化看板")
st.caption("专注内容总结与图文视觉还原，去中心化处理办公内容。")

uploaded_file = st.file_uploader("上传录音转写文本或 PDF 内容文本", type=["txt"])

if uploaded_file and st.button("🚀 生成图文总结看板", type="primary"):
    with st.spinner("🧠 正在构建视觉总结..."):
        content = uploaded_file.read().decode("utf-8")
        final_html = generate_visual_summary(content)
        
        if final_html:
            # 直接在网页端显示带色块的看板
            st.markdown(final_html, unsafe_allow_html=True)
            
            # 提供 Markdown 原始文本下载
            st.download_button("下载纪要文本", final_html, file_name="智能纪要看板.html")
