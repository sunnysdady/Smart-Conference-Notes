import streamlit as st
import requests
import json
import os

# ===================== 1. 基础配置 =====================
st.set_page_config(
    page_title="飞书级智能纪要-极致还原版",
    page_icon="📝",
    layout="wide"
)

# 密钥配置
QWEN_API_KEY = "sk-ecb46034c430477e9c9a4b4fd6589742"
FEISHU_WEBHOOK = st.secrets.get("FEISHU_WEBHOOK", "")

# ===================== 2. CSS 样式注入 (复刻飞书卡片) =====================
st.markdown("""
<style>
    /* 飞书风格卡片容器 */
    .feishu-container {
        background-color: #ffffff;
        border: 1px solid #e5e6eb;
        border-radius: 8px;
        padding: 24px;
        margin-bottom: 20px;
        box-shadow: 0 2px 8px rgba(0,0,0,0.05);
    }
    /* 模块标题 */
    .section-title {
        font-size: 18px;
        font-weight: 600;
        color: #1f2329;
        margin-bottom: 16px;
        display: flex;
        align-items: center;
    }
    /* 状态标签 */
    .tag {
        padding: 2px 8px;
        border-radius: 4px;
        font-size: 12px;
        font-weight: 500;
        margin-left: 8px;
    }
    .tag-green { background-color: #e8f8f2; color: #00b67a; }
    .tag-orange { background-color: #fff7e8; color: #ff9d00; }
    .tag-red { background-color: #fff2f0; color: #f53f3f; }
    
    /* 下一步计划底色 */
    .next-plan {
        background-color: #fff7e8;
        border-radius: 4px;
        padding: 12px;
        border-left: 4px solid #ff9d00;
        margin-top: 15px;
    }
</style>
""", unsafe_allow_html=True)

# ===================== 3. 核心处理逻辑 =====================

def fix_visual_output(text):
    """
    将 AI 输出的结构化文本转换为飞书风格的 HTML 卡片
    """
    # 替换状态标签为带颜色的 HTML
    text = text.replace("[正常推进]", '<span class="tag tag-green">正常推进</span>')
    text = text.replace("[需要优化]", '<span class="tag tag-orange">需要优化</span>')
    text = text.replace("[存在风险]", '<span class="tag tag-red">存在风险</span>')
    
    # 包装主要模块到卡片容器
    if "### 总结" in text:
        parts = text.split("### 总结")
        summary_content = parts[1].split("###")[0]
        card_html = f'''
        <div class="feishu-container">
            <div class="section-title">📊 重点项目概览</div>
            {summary_content}
        </div>
        '''
        text = text.replace(f"### 总结{summary_content}", card_html)
    
    return text

def generate_feishu_pro_summary(content):
    """
    调用通义千问 Qwen-Max，1:1 还原 PDF 样例结构
    """
    url = "https://dashscope.aliyuncs.com/api/v1/services/aigc/text-generation/generation"
    headers = {"Authorization": f"Bearer {QWEN_API_KEY}", "Content-Type": "application/json"}
    
    # 基于 PDF 样例深度优化的 Prompt [cite: 8, 31, 34, 141]
    prompt = f"""
    你现在是飞书（Lark）顶尖 AI 秘书。请根据转录内容，100% 还原飞书原版“智能纪要”的结构和语感。
    
    【输出结构要求】:
    1. ### 总结:
       - 必须包含“重点项目”子模块。
       - 每个项目需带状态标签：[正常推进]、[需要优化] 或 [存在风险]。
       - 提取具体的量化指标（如ROAS、完成件数等）[cite: 15, 16]。
    
    2. ### 运营工作跟进 (表格形式):
       - 列名：工作类别 | 具体内容 | 负责人 | 状态 [cite: 31]。
       - 状态包含：已完成、处理中、待处理、计划中。
    
    3. ### 下一步计划:
       - 💡 开头，总结后续核心动作 [cite: 32]。
    
    4. ### 关键决策:
       - 采用“问题 -> 方案 -> 依据”的严谨逻辑 [cite: 127, 128, 129]。
    
    5. ### 金句时刻:
       - 提取具有决策引导性的原话，并附带简短分析 [cite: 141, 142]。

    6. ### 详细纪要 (智能章节):
       - 使用 ● 和 ■ 符号进行层级划分 [cite: 34, 35, 39]。

    【内容原文】:
    {content}
    """

    payload = {
        "model": "qwen-max",
        "input": {"messages": [{"role": "user", "content": prompt}]},
        "parameters": {"result_format": "text", "temperature": 0.2}
    }

    try:
        response = requests.post(url, headers=headers, json=payload, timeout=60)
        res_json = response.json()
        
        if response.status_code != 200:
            st.error(f"API 报错: {res_json.get('message')}")
            return None
            
        raw_text = res_json.get("output", {}).get("text", "")
        return fix_visual_output(raw_text)
    except Exception as e:
        st.error(f"连接失败: {e}")
        return None

def push_to_feishu(summary_text):
    """推送卡片至飞书机器人"""
    if not FEISHU_WEBHOOK: return
    # 推送前清理 HTML 标签以适应 Markdown 卡片
    clean_md = summary_text.replace('<div class="feishu-container">', "---").replace("</div>", "---")
    clean_md = clean_md.replace('<span class="tag tag-green">', "**").replace("</span>", "**")
    
    payload = {
        "msg_type": "interactive",
        "card": {
            "header": {"title": {"tag": "plain_text", "content": "📅 飞书智能会议纪要"}, "template": "wathet"},
            "elements": [{"tag": "div", "text": {"tag": "lark_md", "content": clean_md}}]
        }
    }
    requests.post(FEISHU_WEBHOOK, json=payload)

# ===================== 4. UI 布局 =====================

st.title("📝 飞书级智能纪要助手 (极致还原版)")
st.caption("基于通义千问 Qwen-Max 引擎，深度复刻原版图文面板与待办表格。")

# 使用分栏布局
col_in, col_out = st.columns([1, 1.5], gap="large")

with col_in:
    st.subheader("📥 输入区域")
    input_text = st.text_area("请粘贴会议转录文本", height=500, placeholder="在此输入...)")
    generate_btn = st.button("🚀 生成并同步飞书", type="primary", use_container_width=True)

with col_out:
    st.subheader("📋 预览区域")
    if generate_btn:
        if not input_text.strip():
            st.warning("内容不能为空")
        else:
            with st.spinner("🧠 正在进行深度语义建模..."):
                final_summary = generate_feishu_pro_summary(input_text)
                if final_summary:
                    # 关键：开启 HTML 渲染以显示卡片容器
                    st.markdown(final_summary, unsafe_allow_html=True)
                    
                    # 自动回传飞书
                    push_to_feishu(final_summary)
                    st.toast("✅ 已成功推送至飞书机器人！", icon="📲")
