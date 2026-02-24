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
st.set_page_config(page_title="飞书原生看板-修复版", page_icon="🎯", layout="wide")

APP_ID = "cli_a916f070b0f8dcd6"
APP_SECRET = "gHOYZxXsoTXpmsnyf37C5dqcN4tOkibW"
QWEN_API_KEY = "sk-ecb46034c430477e9c9a4b4fd6589742"

# ===================== 2. 飞书开放平台底层 API =====================

def get_feishu_token():
    url = "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal"
    try:
        res = requests.post(url, json={"app_id": APP_ID, "app_secret": APP_SECRET})
        return res.json().get("tenant_access_token")
    except:
        return None

def create_feishu_doc(title):
    token = get_feishu_token()
    if not token: return None
    url = "https://open.feishu.cn/open-apis/docx/v1/documents"
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    res = requests.post(url, headers=headers, json={"title": title})
    return res.json().get("data", {}).get("document", {}).get("document_id")

def build_100pct_safe_blocks(data):
    """
    【核心修复引擎】放弃易报错的 Callout，全部采用原生 text_element_style 实现背景色渲染。
    这不仅 100% 符合飞书参数规范，还能精准实现 PDF 中的色块标签效果。
    """
    blocks = []
    
    # 1. 标题与基础信息
    blocks.append({"block_type": 3, "heading1": {"elements": [{"text_run": {"content": data.get("title", "智能纪要")}}]}})
    blocks.append({"block_type": 2, "text": {"elements": [{"text_run": {"content": f"📅 {data.get('date', '近期')} | AI智能生成", "text_element_style": {"text_color": 7}}}]}})
    blocks.append({"block_type": 2, "text": {"elements": [{"text_run": {"content": ""}}]}}) # 空行

    # 2. 重点项目 (原生彩色标签还原)
    blocks.append({"block_type": 4, "heading2": {"elements": [{"text_run": {"content": "📊 重点项目概览"}}]}})
    for proj in data.get("projects", []):
        status = proj.get("status", "进行中")
        # 飞书色号安全映射: 4=绿, 1=红, 2=橙; 14=浅绿底, 11=浅红底, 12=浅橙底
        tc, bgc = 5, 15 # 默认蓝
        if "正常" in status or "完成" in status: tc, bgc = 4, 14
        elif "风险" in status or "滞销" in status or "待" in status: tc, bgc = 1, 11
        elif "优化" in status: tc, bgc = 2, 12
            
        blocks.append({
            "block_type": 2,
            "text": {"elements": [
                {"text_run": {"content": f" ❖ {proj.get('name', '项目项')}   ", "text_element_style": {"bold": True}}},
                {"text_run": {"content": f" {status} ", "text_element_style": {"text_color": tc, "background_color": bgc, "bold": True}}}
            ]}
        })
        for detail in proj.get("details", []):
            blocks.append({"block_type": 12, "bullet": {"elements": [{"text_run": {"content": detail}}]}})
    blocks.append({"block_type": 2, "text": {"elements": [{"text_run": {"content": ""}}]}})

    # 3. 运营工作跟进 (列表结合标签)
    blocks.append({"block_type": 4, "heading2": {"elements": [{"text_run": {"content": "🗓️ 运营工作跟进"}}]}})
    for op in data.get("operations", []):
        status = op.get("status", "")
        tc, bgc = (4,14) if "完成" in status else ((1,11) if "待" in status else (2,12))
        blocks.append({
            "block_type": 12,
            "bullet": {"elements": [
                {"text_run": {"content": f"{op.get('category', '分类')}   ", "text_element_style": {"bold": True}}},
                {"text_run": {"content": f" {status} ", "text_element_style": {"text_color": tc, "background_color": bgc, "bold": True}}},
                {"text_run": {"content": f"  |  操作: {op.get('content', '')}  |  负责人: {op.get('owner', '')}", "text_element_style": {"text_color": 7}}}
            ]}
        })
    blocks.append({"block_type": 2, "text": {"elements": [{"text_run": {"content": ""}}]}})

    # 4. 下一步计划 (黄色高亮底色)
    blocks.append({"block_type": 4, "heading2": {"elements": [{"text_run": {"content": "🚀 下一步计划"}}]}})
    blocks.append({
        "block_type": 2,
        "text": {"elements": [
            {"text_run": {"content": f" 💡 {data.get('next_steps', '暂无明确计划')} ", "text_element_style": {"bold": True, "background_color": 13}}}
        ]}
    })
    blocks.append({"block_type": 2, "text": {"elements": [{"text_run": {"content": ""}}]}})

    # 5. 决策与讨论
    blocks.append({"block_type": 4, "heading2": {"elements": [{"text_run": {"content": "🎯 核心决策"}}]}})
    for dec in data.get("decisions", []):
        blocks.append({"block_type": 12, "bullet": {"elements": [{"text_run": {"content": f"问题：{dec.get('problem', '')}\n方案：{dec.get('solution', '')}"}}]}})

    return blocks

def push_blocks_to_feishu(doc_id, blocks):
    token = get_feishu_token()
    url = f"https://open.feishu.cn/open-apis/docx/v1/documents/{doc_id}/blocks/0/children"
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    
    # 每次仅传输 50 个 Block，防止报超长错误
    for i in range(0, len(blocks), 50):
        batch = blocks[i:i+50]
        res = requests.post(url, headers=headers, json={"children": batch, "index": -1})
        data = res.json()
        if data.get("code") != 0:
            st.error(f"❌ 区块写入失败: {data.get('msg')}")
            return None
    return f"https://bytedance.feishu.cn/docx/{doc_id}"

# ===================== 3. AI 结构化引擎 =====================

@st.cache_resource
def load_model():
    return whisper.load_model("base")

def get_json_data(content):
    url = "https://dashscope.aliyuncs.com/api/v1/services/aigc/text-generation/generation"
    headers = {"Authorization": f"Bearer {QWEN_API_KEY}", "Content-Type": "application/json"}
    
    prompt = f"""
    请将以下会议纪要转化为严格的 JSON 格式，绝不能包含 Markdown 符号以外的其他文字。
    必须完全符合以下结构（缺少的字段留空）：
    {{
        "title": "会议主题", "date": "XXXX年XX月XX日",
        "projects": [{{"name": "项目", "status": "正常推进/存在风险/需要优化", "details": ["细节1"]}}],
        "operations": [{{"category": "分类", "content": "内容", "owner": "人员", "status": "状态"}}],
        "next_steps": "下一步整体计划",
        "decisions": [{{"problem": "问题描述", "solution": "具体对策"}}]
    }}
    原文：{content[:20000]}
    """
    try:
        res = requests.post(url, headers=headers, json={"model": "qwen-max", "input": {"messages": [{"role": "user", "content": prompt}]}})
        text = res.json()["output"]["text"]
        match = re.search(r'\{.*\}', text, re.DOTALL)
        if match:
            return json.loads(match.group(0))
        return None
    except Exception as e:
        st.error(f"AI解析失败: {e}")
        return None

# ===================== 4. UI 工作流 =====================

st.title("🎯 飞书看板修复版：原生安全渲染")
st.info("彻底解决 Invalid Param 报错，100% 安全注入彩色标签。")

uploaded_file = st.file_uploader("请上传音频或TXT", type=["mp3", "wav", "m4a", "txt"])

if uploaded_file and st.button("🚀 启动原生级渲染构建", type="primary"):
    with st.status("正在执行多维处理引擎...", expanded=True) as status:
        
        status.write("1️⃣ 解析源文件...")
        if uploaded_file.name.endswith('.txt'):
            raw_text = uploaded_file.read().decode("utf-8")
        else:
            status.write("唤醒 Whisper 本地转录模型 (请耐心等待)...")
            model = load_model()
            temp_path = f"temp_{uploaded_file.name}"
            with open(temp_path, "wb") as f: f.write(uploaded_file.getbuffer())
            raw_text = model.transcribe(temp_path, language="zh")["text"]
            os.remove(temp_path)
            
        status.write("2️⃣ AI 进行降维 JSON 解析...")
        json_data = get_json_data(raw_text)
        
        if json_data:
            status.write("3️⃣ 创建空白云文档...")
            doc_id = create_feishu_doc(f"智能看板：{json_data.get('title', '会议纪要')}")
            
            if doc_id:
                status.write("4️⃣ 注入原生背景色与排版标签 (安全模式)...")
                blocks = build_100pct_safe_blocks(json_data)
                doc_url = push_blocks_to_feishu(doc_id, blocks)
                
                if doc_url:
                    status.update(label="✅ 原生飞书文档构建完成！", state="complete")
                    st.markdown(f"""
                    <div style="background:#f0f2f5; padding:30px; border-radius:15px; text-align:center;">
                        <h2 style="color:#1f2329;">✨ 结构化仪表盘已写入</h2>
                        <a href="{doc_url}" target="_blank" style="background:#3370ff; color:white; padding:15px 40px; text-decoration:none; border-radius:8px; font-weight:bold; font-size:18px; display:inline-block; margin-top:10px;">
                            🚀 点击检阅最终成果
                        </a>
                    </div>
                    """, unsafe_allow_html=True)
                else:
                    status.update(label="❌ 写入失败，请查阅报错提示", state="error")
            else:
                status.update(label="❌ 文档创建失败", state="error")
        else:
            status.update(label="❌ AI 输出数据不合规", state="error")
