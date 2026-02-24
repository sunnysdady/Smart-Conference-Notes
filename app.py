import streamlit as st
import requests
import json
import os
import re
import whisper
import base64
import zlib
from datetime import datetime

# ===================== 1. 基础配置 =====================
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

st.set_page_config(page_title="飞书智能纪要：高信息密度图文版", page_icon="📈", layout="wide")

APP_ID = "cli_a916f070b0f8dcd6"
APP_SECRET = "gHOYZxXsoTXpmsnyf37C5dqcN4tOkibW"
QWEN_API_KEY = "sk-ecb46034c430477e9c9a4b4fd6589742"

# ===================== 2. 飞书核心 API 引擎 =====================

def get_feishu_token():
    try:
        url = "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal"
        res = requests.post(url, json={"app_id": APP_ID, "app_secret": APP_SECRET}, timeout=10)
        return res.json().get("tenant_access_token")
    except:
        return None

def create_feishu_doc(title):
    token = get_feishu_token()
    if not token: return None
    url = "https://open.feishu.cn/open-apis/docx/v1/documents"
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    safe_title = str(title).strip() if title else "高密度图文纪要"
    res = requests.post(url, headers=headers, json={"title": safe_title})
    return res.json().get("data", {}).get("document", {}).get("document_id")

def generate_and_upload_diagram(doc_id, mermaid_code):
    """【修复痛点】渲染逻辑图，返回 飞书token 和 原始图片bytes 供双端展示"""
    token = get_feishu_token()
    if not token or not mermaid_code or len(mermaid_code) < 10: return None, None
    
    try:
        clean_code = mermaid_code.replace("```mermaid", "").replace("```", "").strip()
        clean_code = clean_code.replace('\\n', '\n')
        
        compressed = zlib.compress(clean_code.encode('utf-8'), 9)
        encoded = base64.urlsafe_b64encode(compressed).decode('ascii')
        img_url = f"https://kroki.io/mermaid/png/{encoded}"
        
        img_res = requests.get(img_url, timeout=20)
        if img_res.status_code != 200: return None, None
            
        img_bytes = img_res.content

        # 上传飞书
        upload_url = "https://open.feishu.cn/open-apis/drive/v1/medias/upload_all"
        headers = {"Authorization": f"Bearer {token}"}
        data = {
            "file_name": "diagram.png", 
            "parent_type": "docx_image", 
            "parent_node": doc_id, 
            "size": len(img_bytes)
        }
        files = {"file": ("diagram.png", img_bytes, "image/png")}
        
        up_res = requests.post(upload_url, headers=headers, data=data, files=files, timeout=15)
        up_data = up_res.json()
        
        if up_data.get("code") != 0: return None, img_bytes
        return up_data.get("data", {}).get("file_token"), img_bytes
    except Exception as e:
        return None, None

# ===================== 3. 高信息密度排版构建器 =====================

def safe_text(content):
    return str(content).replace('\n', ' ').strip() or " "

def empty_line():
    return {"block_type": 2, "text": {"elements": [{"text_run": {"content": " "}}]}}

def build_rich_blocks(data, diagram_file_token=None):
    blocks = []

    # 1. 顶部元数据
    meta = data.get("meta", {})
    blocks.append({"block_type": 3, "heading1": {"elements": [{"text_run": {"content": safe_text(meta.get('theme', '智能纪要'))}}]}})
    blocks.append({"block_type": 2, "text": {"elements": [{"text_run": {"content": f"📅 会议时间: {safe_text(meta.get('time', '近期'))}  |  👥 参会人: {safe_text(meta.get('participants', '与会人员'))}", "text_element_style": {"text_color": 7}}}]}})
    blocks.append(empty_line())

    # 2. 战略级共识 (取代之前的极简速读)
    consensus = data.get("strategic_consensus", [])
    if consensus:
        blocks.append({"block_type": 4, "heading2": {"elements": [{"text_run": {"content": "🎯 战略核心共识"}}]}})
        for point in consensus:
            blocks.append({
                "block_type": 2,
                "text": {"elements": [{"text_run": {"content": f" 💡 {safe_text(point)} ", "text_element_style": {"background_color": 5, "bold": True}}}]} # 蓝色高亮底色
            })
        blocks.append(empty_line())

    # 3. 核心数据看板 (增加图表外的信息丰富度)
    metrics = data.get("key_metrics", [])
    if metrics:
        blocks.append({"block_type": 4, "heading2": {"elements": [{"text_run": {"content": "📊 核心数据看板"}}]}})
        metric_str = "   |   ".join([f"{m.get('label')}: {m.get('value')}" for m in metrics])
        blocks.append({
            "block_type": 2,
            "text": {"elements": [{"text_run": {"content": f" {metric_str} ", "text_element_style": {"background_color": 4, "bold": True}}}]} # 绿色高亮底色
        })
        blocks.append(empty_line())

    # 4. 图文架构图 (补全 width 和 height 参数，防止被飞书拦截)
    if diagram_file_token:
        blocks.append({"block_type": 4, "heading2": {"elements": [{"text_run": {"content": "🗺️ 会议逻辑架构与思维导图"}}]}})
        blocks.append({
            "block_type": 27, 
            "image": {
                "token": diagram_file_token,
                "width": 1200,   # 强制指定宽度
                "height": 800    # 强制指定高度
            }
        })
        blocks.append(empty_line())

    # 5. 议题深度下钻 (解决内容太少的问题)
    topics = data.get("topics", [])
    if topics:
        blocks.append({"block_type": 4, "heading2": {"elements": [{"text_run": {"content": "📝 核心议题详述"}}]}})
        for idx, topic in enumerate(topics):
            # 蓝色议题标题
            blocks.append({"block_type": 5, "heading3": {"elements": [{"text_run": {"content": f"{idx+1}. {safe_text(topic.get('title'))}", "text_element_style": {"text_color": 5}}}]}})
            # 极度详实的子弹点
            for detail in topic.get("details", []):
                blocks.append({"block_type": 12, "bullet": {"elements": [{"text_run": {"content": safe_text(detail)}}]}})
            # 结论引导
            conclusion = safe_text(topic.get("conclusion", ""))
            if conclusion and conclusion != " ":
                blocks.append({"block_type": 2, "text": {"elements": [{"text_run": {"content": f" ➔ 结论决议: {conclusion} ", "text_element_style": {"bold": True, "background_color": 7}}}]}}) # 灰色高亮
            blocks.append(empty_line())

    # 6. 行动与待办
    todos = data.get("todos", [])
    if todos:
        blocks.append({"block_type": 4, "heading2": {"elements": [{"text_run": {"content": "✅ 行动与待办矩阵"}}]}})
        for todo in todos:
            task = safe_text(todo.get("task"))
            owner = safe_text(todo.get("owner"))
            blocks.append({"block_type": 17, "todo": {"style": {"done": False}, "elements": [{"text_run": {"content": f"由 @{owner} 负责: {task}"}}] }})
        blocks.append(empty_line())

    # 7. 智能章节
    chapters = data.get("chapters", [])
    if chapters:
        blocks.append({"block_type": 4, "heading2": {"elements": [{"text_run": {"content": "⏱️ 原声回溯与节点"}}]}})
        for chap in chapters:
            time_str = safe_text(chap.get("time"))
            title_str = safe_text(chap.get("title"))
            blocks.append({"block_type": 12, "bullet": {"elements": [
                {"text_run": {"content": f"[{time_str}] {title_str}: ", "text_element_style": {"bold": True}}},
                {"text_run": {"content": safe_text(chap.get("summary")), "text_element_style": {"text_color": 7}}}
            ]}})

    return blocks

def push_blocks_to_feishu(doc_id, blocks):
    token = get_feishu_token()
    url = f"https://open.feishu.cn/open-apis/docx/v1/documents/{doc_id}/blocks/{doc_id}/children"
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    
    for i in range(0, len(blocks), 40):
        batch = blocks[i:i+40]
        try:
            res = requests.post(url, headers=headers, json={"children": batch}, timeout=15)
            if res.json().get("code") != 0:
                for block in batch: # 单行重试保护
                    requests.post(url, headers=headers, json={"children": [block]})
        except Exception:
            pass
    return f"https://bytedance.feishu.cn/docx/{doc_id}"

# ===================== 4. 商业提炼引擎 (增强扩写能力) =====================

@st.cache_resource
def load_model():
    return whisper.load_model("base")

def get_json_data(content):
    url = "https://dashscope.aliyuncs.com/api/v1/services/aigc/text-generation/generation"
    headers = {"Authorization": f"Bearer {QWEN_API_KEY}", "Content-Type": "application/json"}
    
    prompt = f"""
    你是一名身经百战的顶级商业咨询顾问。请将下方的会议逐字稿转化为【高信息密度】、【细节丰富】的结构化商业报告。
    
    【致命警告】：彻底摒弃“流水账”和“极度压缩”的摘要方式！在 `details` 数组中，每条细节字数不得少于 60 字！必须原汁原味地保留会议中提到的“具体业务数字”、“客户案例”、“实际难点”和“明确的落地模式”，让未参会的人也能完全看懂上下文。
    
    【输出结构必须严格为 JSON】：
    {{
        "meta": {{ "theme": "会议主题", "time": "推测时间", "participants": "发言人" }},
        "strategic_consensus": [
            "用详细的商业话术总结会议达成的第1个核心共识(不少于30字)",
            "用详细的商业话术总结会议达成的第2个核心共识(不少于30字)"
        ],
        "key_metrics": [
            {{ "label": "数据指标名称(如:海外仓面积)", "value": "具体数值(如:3.3万平)" }},
            {{ "label": "指标2", "value": "数值2" }}
        ],
        "mermaid_code": "graph TD\\\\nA[核心主题] --> B(关键议题)\\\\nB --> C(得出的结论)\\\\nA --> D(其他要点)",
        "topics": [
            {{
                "title": "议题名称",
                "details": [
                    "细节1：(字数不少于60字，必须包含具体数据、背景或难点)",
                    "细节2：(字数不少于60字，必须详细阐述方案逻辑)"
                ],
                "conclusion": "该议题的最终落地决议"
            }}
        ],
        "todos": [ {{ "task": "具体行动指令", "owner": "负责人" }} ],
        "chapters": [ {{ "time": "00:00:00", "title": "节点", "summary": "说明" }} ]
    }}
    
    【防崩溃注意】：mermaid_code 中的换行必须写为真正的 \\\\n，且节点内禁止使用大括号等特殊符号。
    
    原文内容：{content[:25000]}
    """
    
    try:
        res = requests.post(url, headers=headers, json={"model": "qwen-max", "input": {"messages": [{"role": "user", "content": prompt}]}}, timeout=180)
        text = res.json().get("output", {}).get("text", "")
        match = re.search(r'\{.*\}', text, re.DOTALL)
        if match: return json.loads(match.group(0), strict=False)
        return None
    except Exception as e:
        st.error(f"❌ AI 接口异常: {e}")
        return None

# ===================== 5. 主控 UI =====================

st.title("📈 飞书智能纪要：高密度图文重构版")
st.info("彻底解决内容干瘪问题，引入【核心数据看板】与【强制长文本展开】机制；双端同步渲染架构图！")

uploaded_file = st.file_uploader("请上传会议文件 (TXT/Audio)", type=["mp3", "wav", "m4a", "txt"])

if uploaded_file and st.button("🚀 生成高密度图文纪要", type="primary"):
    with st.status("正在启动高密度图文架构引擎...", expanded=True) as status:
        
        status.write("1️⃣ 解析输入文件...")
        if uploaded_file.name.endswith('.txt'):
            raw_text = uploaded_file.read().decode("utf-8")
        else:
            status.write("正在提取带时间戳的语音切片...")
            model = load_model()
            temp_path = f"temp_{uploaded_file.name}"
            with open(temp_path, "wb") as f: f.write(uploaded_file.getbuffer())
            
            result = model.transcribe(temp_path, language="zh")
            raw_text = "".join([f"[{int(seg['start']//60):02d}:{int(seg['start']%60):02d}] {seg['text']}\n" for seg in result["segments"]])
            os.remove(temp_path)
            
        status.write("2️⃣ 顶级商业 AI 正在进行信息扩容与架构提炼 (预计需 1-2 分钟)...")
        json_data = get_json_data(raw_text)
        
        if json_data:
            status.write("3️⃣ 建立云端通道...")
            doc_id = create_feishu_doc(json_data.get('meta', {}).get('theme', '高密度图文纪要'))
            
            if doc_id:
                status.write("4️⃣ 正在渲染高清架构图片...")
                mermaid_code = json_data.get("mermaid_code")
                diagram_token, img_bytes = generate_and_upload_diagram(doc_id, mermaid_code) if mermaid_code else (None, None)
                
                if diagram_token:
                    status.write("✔️ 架构图上传飞书成功！")
                elif img_bytes:
                    status.write("⚠️ 图片未能插入文档，但已在网页端为您保留。")
                
                status.write("5️⃣ 注入高密度深层排版...")
                blocks = build_rich_blocks(json_data, diagram_token)
                doc_url = push_blocks_to_feishu(doc_id, blocks)
                
                if doc_url:
                    status.update(label="✅ 原生飞书高密度纪要生成成功！", state="complete")
                    
                    # 【核心体验升级】在网页端直接展示图表，所见即所得！
                    if img_bytes:
                        st.markdown("### 📊 本次会议逻辑架构图预览")
                        st.image(img_bytes, use_column_width=True)
                    
                    st.markdown(f"""
                    <div style="background:#f0f2f5; padding:30px; border-radius:15px; text-align:center;">
                        <h2 style="color:#1f2329;">🎉 高密度商业看板已就绪</h2>
                        <p style="color:#646a73;">全量保留业务数字与落地细节，参会者可无障碍阅览！</p>
                        <a href="{doc_url}" target="_blank" style="background:#3370ff; color:white; padding:15px 40px; text-decoration:none; border-radius:8px; font-weight:bold; font-size:18px; display:inline-block; margin-top:10px;">
                            🚀 立即检阅您的专属纪要
                        </a>
                    </div>
                    """, unsafe_allow_html=True)
                else:
                    status.update(label="❌ 写入异常，请检查日志", state="error")
            else:
                status.update(label="❌ 文档创建失败", state="error")
        else:
            status.update(label="❌ 进程中止，提炼失败", state="error")
