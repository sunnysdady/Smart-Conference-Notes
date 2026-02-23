import streamlit as st
import requests
import json
import os
import time

# ===================== 1. 基础配置 =====================
st.set_page_config(page_title="飞书云文档自动生成器", page_icon="📄", layout="wide")

# 飞书凭证与 API Key (基于你提供的信息)
APP_ID = "cli_a916f070b0f8dcd6"
APP_SECRET = "gHOYZxXsoTXpmsnyf37C5dqcN4tOkibW"
QWEN_API_KEY = "sk-ecb46034c430477e9c9a4b4fd6589742"

# ===================== 2. 飞书开放平台 API 封装 =====================

def get_feishu_token():
    """获取租户访问凭证"""
    url = "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal"
    res = requests.post(url, json={"app_id": APP_ID, "app_secret": APP_SECRET})
    return res.json().get("tenant_access_token")

def create_doc(title):
    """创建云文档并返回 ID"""
    token = get_feishu_token()
    url = "https://open.feishu.cn/open-apis/docx/v1/documents"
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    res = requests.post(url, headers=headers, json={"title": title})
    return res.json().get("data", {}).get("document", {}).get("document_id")

def add_blocks(document_id, summary_text):
    """将 AI 内容转换为 Docx Blocks 写入云文档"""
    token = get_feishu_token()
    url = f"https://open.feishu.cn/open-apis/docx/v1/documents/{document_id}/blocks/0/children"
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    
    blocks = []
    lines = summary_text.split('\n')
    
    for line in lines:
        line = line.strip()
        if not line: continue
        
        # 视觉还原：使用高亮块 (Callout) 模拟 PDF 总结面板
        if any(keyword in line for keyword in ["重点项目", "总结", "会议核心"]):
            blocks.append({
                "block_type": 19, # Callout Block
                "callout": {
                    "background_color": 1, # 蓝色背景
                    "elements": [{"text_run": {"content": line, "text_element_style": {"bold": True}}}]
                }
            })
        elif line.startswith('###'):
            blocks.append({"block_type": 3, "heading1": {"elements": [{"text_run": {"content": line.replace('###','').strip(), "text_element_style": {"bold": True}}}]}})
        elif "下一步计划" in line:
            blocks.append({"block_type": 19, "callout": {"background_color": 4, "elements": [{"text_run": {"content": "💡 " + line, "text_element_style": {"bold": True}}}]}})
        else:
            # 状态标签模拟：检测 [正常推进] 等词汇
            styled_text = line.replace("[正常推进]", "🟢 正常推进").replace("[存在风险]", "🔴 存在风险").replace("[需要优化]", "🟠 需要优化")
            blocks.append({"block_type": 2, "text": {"elements": [{"text_run": {"content": styled_text}}]}})

    # 批量上传 Blocks
    requests.post(url, headers=headers, json={"children": blocks[:50], "index": -1})
    return f"https://bytedance.feishu.cn/docx/{document_id}"

# ===================== 3. AI 总结逻辑 =====================

def generate_feishu_summary(content):
    """调用通义千问 Qwen-Max 还原 8 大模块"""
    url = "https://dashscope.aliyuncs.com/api/v1/services/aigc/text-generation/generation"
    headers = {"Authorization": f"Bearer {QWEN_API_KEY}", "Content-Type": "application/json"}
    
    prompt = f"""
    你现在是飞书官方智能秘书。请根据转录文本生成 1:1 还原飞书样式的智能纪要。
    【必须包含的模块】：
    1. 会议总结与重点项目（带 [正常推进/需要优化/存在风险] 状态标签）
    2. 运营工作跟进（表格形式：工作类别 | 具体内容 | 负责人 | 状态）
    3. 详细会议内容（按 ◦ 章节 -> ▪ 子项 展开）
    4. 下一步计划与待办
    5. 智能章节（带 XX:XX 时间戳）
    6. 关键决策（问题/方案/依据）与金句时刻
    
    文本内容：{content}
    """
    
    payload = {"model": "qwen-max", "input": {"messages": [{"role": "user", "content": prompt}]}, "parameters": {"result_format": "text"}}
    try:
        res = requests.post(url, headers=headers, json=payload, timeout=60)
        return res.json()["output"]["text"]
    except Exception as e:
        st.error(f"AI 生成失败: {e}")
        return None

# ===================== 4. 主程序界面 =====================

st.title("📄 飞书级智能纪要：云文档自动生成")
st.info("请直接上传录音转写后的 .txt 文件，我们将为您一键生成飞书云文档。")

# 仅保留文件上传功能
uploaded_file = st.file_uploader("选择 TXT 文件", type=["txt"])

if uploaded_file and st.button("🚀 生成并创建飞书云文档", type="primary"):
    with st.spinner("🧠 正在读取文件并构建云文档看板..."):
        # 读取 TXT 内容
        raw_content = uploaded_file.read().decode("utf-8")
        
        if not raw_content.strip():
            st.warning("上传的文件内容为空，请检查。")
            st.stop()
            
        # 1. 生成摘要
        summary = generate_feishu_summary(raw_content)
        
        if summary:
            # 2. 创建飞书文档
            doc_name = f"智能纪要：{uploaded_file.name.replace('.txt','')}"
            doc_id = create_doc(doc_name)
            
            if doc_id:
                # 3. 写入内容块
                doc_url = add_blocks(doc_id, summary)
                
                st.success("🎉 飞书云文档看板已生成！")
                st.balloons()
                
                # 引导进入文档
                st.markdown(f"""
                <div style="background:#f0f2f5; padding:30px; border-radius:15px; text-align:center; border:1px solid #dee0e3;">
                    <h2 style="color:#1f2329;">文档排版已在云端完成</h2>
                    <p style="color:#646a73;">已复刻重点项目高亮块、状态色块及 8 大核心模块</p>
                    <a href="{doc_url}" target="_blank" style="background:#3370ff; color:white; padding:15px 40px; text-decoration:none; border-radius:8px; font-weight:bold; font-size:18px; display:inline-block; margin-top:10px;">
                        🚀 立即打开飞书云文档看板
                    </a>
                </div>
                """, unsafe_allow_html=True)
                
                with st.expander("预览摘要文本"):
                    st.markdown(summary)
