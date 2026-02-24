import streamlit as st
import requests
import json
import os
import re
import whisper
import time
from dotenv import load_dotenv

# ===================== 1. 基础配置 =====================
load_dotenv()
st.set_page_config(page_title="飞书智能看板-修复版", page_icon="🛠️", layout="wide")

APP_ID = "cli_a916f070b0f8dcd6"
APP_SECRET = "gHOYZxXsoTXpmsnyf37C5dqcN4tOkibW"
QWEN_API_KEY = "sk-ecb46034c430477e9c9a4b4fd6589742"

# ===================== 2. 飞书 API (带诊断功能) =====================

def get_feishu_token():
    url = "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal"
    try:
        res = requests.post(url, json={"app_id": APP_ID, "app_secret": APP_SECRET})
        data = res.json()
        if "tenant_access_token" not in data:
            st.error(f"鉴权失败: {data}")
            return None
        return data["tenant_access_token"]
    except Exception as e:
        st.error(f"网络请求失败: {e}")
        return None

def create_feishu_doc(title):
    token = get_feishu_token()
    if not token: return None
    url = "https://open.feishu.cn/open-apis/docx/v1/documents"
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    res = requests.post(url, headers=headers, json={"title": title})
    data = res.json()
    if data.get("code") != 0:
        st.error(f"创建文档失败: {data}")
        return None
    return data.get("data", {}).get("document", {}).get("document_id")

def push_blocks_to_feishu(doc_id, blocks):
    """
    【核心修复】批量写入 Block，并捕获错误
    """
    token = get_feishu_token()
    url = f"https://open.feishu.cn/open-apis/docx/v1/documents/{doc_id}/blocks/0/children"
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    
    # 分批写入，每批 50 个，防止包体过大
    batch_size = 50
    for i in range(0, len(blocks), batch_size):
        batch = blocks[i:i+batch_size]
        payload = {"children": batch, "index": -1}
        
        try:
            res = requests.post(url, headers=headers, json=payload)
            res_data = res.json()
            # 显性报错：如果 code != 0，说明写入失败
            if res_data.get("code") != 0:
                st.error(f"❌ 区块写入失败 (Batch {i//batch_size + 1}): {res_data}")
                st.json(batch) # 打印出有问题的 block 供调试
                return None
        except Exception as e:
            st.error(f"写入请求异常: {e}")
            return None
            
    return f"https://bytedance.feishu.cn/docx/{doc_id}"

# ===================== 3. 稳健的 Block 构建引擎 =====================

def build_safe_feishu_blocks(data):
    """
    使用 Callout (高亮块) 替代易报错的 Text Style，确保 100% 成功率
    """
    blocks = []
    
    # 1. 标题区
    blocks.append({"block_type": 3, "heading1": {"elements": [{"text_run": {"content": data.get("title", "会议纪要")}}]}})
    blocks.append({"block_type": 2, "text": {"elements": [{"text_run": {"content": f"📅 {data.get('date', '')} | AI生成", "text_element_style": {"text_color": 5}}}]}})

    # 2. 重点项目 (使用 Callout 模拟彩色卡片)
    blocks.append({"block_type": 4, "heading2": {"elements": [{"text_run": {"content": "📊 重点项目概览"}}]}})
    
    for proj in data.get("projects", []):
        status = proj.get("status", "进行中")
        # 映射背景色: 5=蓝(默认), 4=绿(正常), 1=红(风险), 2=橙(优化)
        bg_color = 5 
        if "正常" in status or "完成" in status: bg_color = 4
        elif "风险" in status or "滞销" in status: bg_color = 1
        elif "优化" in status: bg_color = 2
        
        # 构造高亮块 (Callout)
        blocks.append({
            "block_type": 19, 
            "callout": {
                "background_color": bg_color,
                "elements": [
                    {"text_run": {"content": f"【{status}】{proj.get('name', '项目')}", "text_element_style": {"bold": True}}},
                    {"text_run": {"content": "\n" + "\n".join([f"• {d}" for d in proj.get('details', [])])}}
                ]
            }
        })

    # 3. 运营工作 (列表)
    blocks.append({"block_type": 4, "heading2": {"elements": [{"text_run": {"content": "🗓️ 运营工作跟进"}}]}})
    for op in data.get("operations", []):
        icon = "🟢" if "完成" in op.get("status","") else ("🔴" if "待" in op.get("status","") else "🟠")
        content_text = f"{icon} {op.get('category')} | {op.get('content')} | 👤 {op.get('owner')}"
        blocks.append({"block_type": 12, "bullet": {"elements": [{"text_run": {"content": content_text}}]}})

    # 4. 下一步计划 (黄色高亮块)
    blocks.append({"block_type": 4, "heading2": {"elements": [{"text_run": {"content": "🚀 下一步计划"}}]}})
    blocks.append({
        "block_type": 19,
        "callout": {
            "background_color": 3, # 黄色
            "elements": [{"text_run": {"content": f"💡 {data.get('next_steps', '暂无计划')}", "text_element_style": {"bold": True}}}]
        }
    })

    # 5. 决策与金句
    blocks.append({"block_type": 4, "heading2": {"elements": [{"text_run": {"content": "🎯 决策与金句"}}]}})
    for dec in data.get("decisions", []):
        blocks.append({"block_type": 12, "bullet": {"elements": [{"text_run": {"content": f"决策：{dec.get('problem')} → {dec.get('solution')}"}}]}})
    
    return blocks

# ===================== 4. AI 核心逻辑 =====================

@st.cache_resource
def load_model():
    return whisper.load_model("base")

def get_json_data(content):
    """提取 JSON，失败则返回空结构以防报错"""
    url = "https://dashscope.aliyuncs.com/api/v1/services/aigc/text-generation/generation"
    headers = {"Authorization": f"Bearer {QWEN_API_KEY}", "Content-Type": "application/json"}
    prompt = f"""
    请将以下会议纪要转化为严格的 JSON 格式。
    结构：{{
        "title": "主题", "date": "时间",
        "projects": [{{"name": "项目名", "status": "正常/风险/优化", "details": ["要点1"]}}],
        "operations": [{{"category": "类别", "content": "内容", "owner": "人", "status": "状态"}}],
        "next_steps": "下一步",
        "decisions": [{{"problem": "问题", "solution": "解法"}}]
    }}
    原文：{content[:20000]}
    """
    try:
        res = requests.post(url, headers=headers, json={"model": "qwen-max", "input": {"messages": [{"role": "user", "content": prompt}]}})
        text = res.json()["output"]["text"]
        match = re.search(r'\{.*\}', text, re.DOTALL)
        return json.loads(match.group(0)) if match else None
    except:
        return None

# ===================== 5. UI 界面 =====================

st.title("🛠️ 飞书看板修复版：原生渲染")
uploaded_file = st.file_uploader("上传文件 (TXT/Audio)", type=["txt", "mp3", "wav", "m4a"])

if uploaded_file and st.button("🚀 重新生成并诊断"):
    with st.status("正在执行全链路诊断...", expanded=True) as status:
        
        # 1. 提取文本
        status.write("1️⃣ 读取文件内容...")
        if uploaded_file.name.endswith('.txt'):
            text = uploaded_file.read().decode("utf-8")
        else:
            model = load_model()
            with open("temp_audio", "wb") as f: f.write(uploaded_file.getbuffer())
            text = model.transcribe("temp_audio", language="zh")["text"]
            
        # 2. 生成数据
        status.write("2️⃣ AI 结构化解析...")
        data = get_json_data(text)
        if not data:
            status.update(label="❌ AI 解析失败，未能生成 JSON", state="error")
            st.stop()
            
        # 3. 创建文档
        status.write("3️⃣ 创建空白云文档...")
        doc_id = create_feishu_doc(data.get("title", "智能纪要"))
        if not doc_id:
            status.update(label="❌ 文档创建失败 (请检查 App ID 权限)", state="error")
            st.stop()
            
        # 4. 写入 Block (核心步骤)
        status.write("4️⃣ 注入原生高亮块 (Safe Mode)...")
        blocks = build_safe_feishu_blocks(data)
        doc_url = push_blocks_to_feishu(doc_id, blocks)
        
        if doc_url:
            status.update(label="✅ 成功！文档已写入", state="complete")
            st.success("🎉 看板生成成功！")
            st.markdown(f'<a href="{doc_url}" target="_blank" style="background:#3370ff;color:white;padding:15px 30px;border-radius:5px;text-decoration:none;">🚀 打开飞书云文档</a>', unsafe_allow_html=True)
        else:
            status.update(label="❌ 写入失败，请查看上方错误日志", state="error")
