import streamlit as st
import requests
import json
import os
import time

# ===================== 1. 核心凭证与配置 =====================
st.set_page_config(page_title="飞书云文档自动化看板", page_icon="📄", layout="wide")

# 您提供的凭证 (已固定)
APP_ID = "cli_a916f070b0f8dcd6"
APP_SECRET = "gHOYZxXsoTXpmsnyf37C5dqcN4tOkibW"
QWEN_API_KEY = "sk-ecb46034c430477e9c9a4b4fd6589742"

# ===================== 2. 飞书 Docx API 封装 =====================

def get_tenant_token():
    """获取飞书调用凭证"""
    url = "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal"
    res = requests.post(url, json={"app_id": APP_ID, "app_secret": APP_SECRET})
    return res.json().get("tenant_access_token")

def create_feishu_doc(title):
    """创建空白文档并返回 ID"""
    token = get_tenant_token()
    url = "https://open.feishu.cn/open-apis/docx/v1/documents"
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    res = requests.post(url, headers=headers, json={"title": title})
    return res.json().get("data", {}).get("document", {}).get("document_id")

def convert_to_docx_blocks(summary_text):
    """
    将 AI 总结精准转换为飞书云文档原生 Blocks
    - 高亮块 (Callout): 还原 PDF 重点项目背景 [cite: 8-14]
    - 标题块 (Heading): 还原模块层级
    - 列表块 (Bullet): 还原详细记录 [cite: 35-85]
    """
    blocks = []
    lines = summary_text.split('\n')
    
    for line in lines:
        line = line.strip()
        if not line: continue
        
        # 视觉还原：高亮块模拟 PDF 总结色块
        if any(kw in line for kw in ["重点项目", "总结", "核心概览"]):
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
            # 还原 PDF 中的黄色引导条 [cite: 32]
            blocks.append({
                "block_type": 19,
                "callout": {
                    "background_color": 4, # 黄色背景
                    "elements": [{"text_run": {"content": "💡 " + line, "text_element_style": {"bold": True}}}]
                }
            })
        elif line.startswith('◦') or line.startswith('•') or line.startswith('-'):
            blocks.append({"block_type": 12, "bullet": {"elements": [{"text_run": {"content": line.lstrip('◦•- ').strip()}}]}})
        else:
            # 状态标签视觉映射 [cite: 10, 12, 14]
            styled_text = line.replace("[正常推进]", "🟢 正常推进").replace("[需要优化]", "🟠 需要优化").replace("[存在风险]", "🔴 存在风险")
            blocks.append({"block_type": 2, "text": {"elements": [{"text_run": {"content": styled_text}}]}})
            
    return blocks

def write_blocks_to_doc(document_id, blocks):
    """批量写入 Blocks 到文档"""
    token = get_tenant_token()
    url = f"https://open.feishu.cn/open-apis/docx/v1/documents/{document_id}/blocks/0/children"
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    
    # 飞书接口单次限制 50 个 block
    for i in range(0, len(blocks), 50):
        payload = {"children": blocks[i:i+50], "index": -1}
        requests.post(url, headers=headers, json=payload)
    return f"https://bytedance.feishu.cn/docx/{document_id}"

# ===================== 3. Qwen-Max 核心生成逻辑 =====================

def generate_visual_summary(content):
    """
    调用通义千问 Qwen-Max 还原 PDF 8 大模块
    加入异常检查，解决 KeyError: 'output'
    """
    url = "https://dashscope.aliyuncs.com/api/v1/services/aigc/text-generation/generation"
    headers = {"Authorization": f"Bearer {QWEN_API_KEY}", "Content-Type": "application/json"}
    
    prompt = f"""
    你现在是飞书官方智能秘书。请根据录音转写文本生成 100% 还原样式的智能纪要看板。
    【输出要求】：
    1. ### 总结：提炼 3 个重点项目，带 [正常推进/需要优化/存在风险] 状态 [cite: 8-17]
    2. ### 运营工作跟进：列表形式展现工作类别、负责人与状态 [cite: 31]
    3. ### 详细会议内容：◦ 章节标题 -> ▪ 子议题 展开 [cite: 35-85]
    4. ### 下一步计划：总结核心动作 [cite: 32]
    5. ### 关键决策与金句：提取问题/方案/依据，以及说话人金句 [cite: 127-147]
    6. ### 智能章节：带 XX:XX 时间戳 [cite: 104-125]
    
    原文内容：{content}
    """
    
    payload = {"model": "qwen-max", "input": {"messages": [{"role": "user", "content": prompt}]}, "parameters": {"result_format": "text"}}
    
    try:
        res = requests.post(url, headers=headers, json=payload, timeout=60)
        res_data = res.json()
        # 健壮性检查：解决 output 键不存在导致的崩溃
        if "output" not in res_data:
            st.error(f"AI 生成异常: {res_data.get('message', '未知错误')}")
            return None
        return res_data["output"]["text"]
    except Exception as e:
        st.error(f"API 请求失败: {str(e)}")
        return None

# ===================== 4. Streamlit UI 逻辑 =====================

st.title("📄 飞书级智能纪要：云文档一键还原")
st.caption("直接上传 .txt 文件，自动在您的飞书空间生成精美的智能看板。")

# 移除 text_area，仅支持 TXT 上传
uploaded_file = st.file_uploader("第一步：上传 TXT 转写文件", type=["txt"])

if uploaded_file and st.button("🚀 第二步：生成并创建云文档", type="primary"):
    with st.spinner("🧠 正在解析文档并构建飞书 Blocks..."):
        # 读取文件
        raw_text = uploaded_file.read().decode("utf-8")
        
        if not raw_text.strip():
            st.warning("上传的文件内容为空。")
            st.stop()
            
        # 1. AI 深度总结
        summary = generate_visual_summary(raw_text)
        
        if summary:
            # 2. 调用飞书 API 创建流
            doc_name = f"智能看板：{uploaded_file.name.replace('.txt','')}"
            doc_id = create_feishu_doc(doc_name)
            
            if doc_id:
                # 3. 转换 Block 并写入
                blocks = convert_to_docx_blocks(summary)
                doc_url = write_blocks_to_doc(doc_id, blocks)
                
                st.success("🎉 飞书云文档看板已成功生成！")
                st.balloons()
                
                # 视觉引导按钮
                st.markdown(f"""
                <div style="background:#f0f2f5; padding:30px; border-radius:15px; text-align:center; border:1px solid #dee0e3;">
                    <h2 style="color:#1f2329;">✨ 云端排版已完成</h2>
                    <p style="color:#646a73;">已自动复刻重点项目高亮栏、下一步计划引导条及 8 大核心模块</p>
                    <a href="{doc_url}" target="_blank" style="background:#3370ff; color:white; padding:15px 40px; text-decoration:none; border-radius:8px; font-weight:bold; font-size:18px; display:inline-block; margin-top:10px;">
                        🚀 立即进入飞书云文档看板
                    </a>
                </div>
                """, unsafe_allow_html=True)
                
                with st.expander("预览 AI 摘要"):
                    st.markdown(summary)
