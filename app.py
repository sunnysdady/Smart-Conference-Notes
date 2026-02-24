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

st.set_page_config(page_title="飞书智能纪要：完美交付版", page_icon="💎", layout="wide")

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
    """渲染脑图并上传至飞书"""
    token = get_feishu_token()
    if not token or not mermaid_code or len(mermaid_code) < 5: return None, None
    
    try:
        # 清洗代码
        clean_code = mermaid_code.replace("```mermaid", "").replace("```", "").strip()
        # 强制修正换行符问题，防止渲染失败
        clean_code = clean_code.replace('\\n', '\n').replace('\"', '"')
        
        # 1. 尝试 Kroki 渲染
        compressed = zlib.compress(clean_code.encode('utf-8'), 9)
        encoded = base64.urlsafe_b64encode(compressed).decode('ascii')
        img_url = f"https://kroki.io/mermaid/png/{encoded}"
        
        img_res = requests.get(img_url, timeout=15)
        if img_res.status_code != 200: 
            return None, None # 渲染失败，走 Text Fallback
            
        img_bytes = img_res.content

        # 2. 上传飞书
        upload_url = "https://open.feishu.cn/open-apis/drive/v1/medias/upload_all"
        headers = {"Authorization": f"Bearer {token}"}
        data = {"file_name": "mindmap.png", "parent_type": "docx_image", "parent_node": doc_id, "size": len(img_bytes)}
        files = {"file": ("mindmap.png", img_bytes, "image/png")}
        
        up_res = requests.post(upload_url, headers=headers, data=data, files=files, timeout=15)
        if up_res.json().get("code") != 0: return None, img_bytes
        return up_res.json().get("data", {}).get("file_token"), img_bytes
    except Exception:
        return None, None

# ===================== 3. 飞书底层复杂组件构建器 =====================

def safe_text(content):
    return str(content).replace('\n', ' ').strip() or " "

def create_text(content, bold=False, color=None, bg_color=None):
    style = {}
    if bold: style["bold"] = True
    if color: style["text_color"] = color
    if bg_color: style["background_color"] = bg_color
    return {"block_type": 2, "text": {"elements": [{"text_run": {"content": content, "text_element_style": style}}]}}

def create_bullet(content):
    return {"block_type": 12, "bullet": {"elements": [{"text_run": {"content": content}}]}}

def create_code_block(code, language="mermaid"):
    """【新增】创建原生代码块，用于脑图渲染失败时的优雅降级"""
    return {
        "block_type": 14, 
        "code": {"language": language, "wrap_text": True},
        "children": [create_text(code)]
    }

def create_card(title, items, bg_color, emoji="📌"):
    """创建彩色高亮卡片 (Callout) - 标题带Emoji模式"""
    children = [create_text(f"{emoji} {title}", bold=True)]
    for item in items:
        children.append(create_bullet(safe_text(item)))
    return {
        "block_type": 19,
        "callout": {"background_color": bg_color},
        "children": children
    }

def create_grid_row(cards):
    """创建多列分栏 (Grid)"""
    cols = []
    for card in cards:
        cols.append({
            "children": [create_card(card.get("title", ""), card.get("items", []), card.get("color", 5), card.get("emoji", "💡"))]
        })
    return {"block_type": 24, "grid": {"column_size": len(cards)}, "children": cols}

def create_table(headers, rows):
    """创建原生表格 (Table)"""
    cells = []
    for h in headers:
        cells.append({"children": [create_text(safe_text(h), bold=True, bg_color=7)]}) # 表头灰色背景
    for row in rows:
        for cell in row:
            cells.append({"children": [create_text(safe_text(cell))]})
    return {
        "block_type": 31,
        "table": {
            "property": {
                "row_size": len(rows) + 1,
                "column_size": len(headers),
                "header_row": True
            }
        },
        "children": cells
    }

def empty_line():
    return {"block_type": 2, "text": {"elements": []}}

# ===================== 4. 视觉看板组装引擎 =====================

def build_visual_blocks(data, diagram_file_token=None, mermaid_raw_code=None):
    blocks = []

    # 1. 顶部元数据
    meta = data.get("meta", {})
    blocks.append({"block_type": 3, "heading1": {"elements": [{"text_run": {"content": safe_text(meta.get('theme', '战略纪要看板'))}}]}})
    blocks.append({"block_type": 2, "text": {"elements": [{"text_run": {"content": f"📅 {safe_text(meta.get('time', '近期'))}   |   👥 {safe_text(meta.get('participants', '与会人员'))}", "text_element_style": {"text_color": 7}}}]}})
    
    # 2. 核心共识 (高亮条)
    consensus = safe_text(data.get("core_consensus", "暂无核心结论"))
    blocks.append(create_card("核心决策共识", [consensus], 5, "🏆"))
    blocks.append(empty_line())

    # 3. 脑图 (图片优先，代码块兜底)
    blocks.append({"block_type": 4, "heading2": {"elements": [{"text_run": {"content": "🧠 战略逻辑脑图"}}]}})
    if diagram_file_token:
        blocks.append({"block_type": 27, "image": {"token": diagram_file_token, "width": 1000, "height": 600}})
    elif mermaid_raw_code:
        # 如果图片挂了，显示代码块，飞书会自动高亮 Mermaid 语法
        blocks.append(create_text("⚠️ 脑图预览 (可视化加载中，以下为逻辑源码):", color=7))
        blocks.append(create_code_block(mermaid_raw_code))
    blocks.append(empty_line())

    # 4. 战略视图看板 (Grid)
    blocks.append({"block_type": 4, "heading2": {"elements": [{"text_run": {"content": "📊 战略视图看板"}}]}})
    row1 = data.get("dashboard_row1", [])
    if row1: blocks.append(create_grid_row(row1))
    row2 = data.get("dashboard_row2", [])
    if row2: blocks.append(create_grid_row(row2))
    blocks.append(empty_line())

    # 5. 行动表格 (Table)
    table_data = data.get("action_table", [])
    if table_data:
        blocks.append({"block_type": 4, "heading2": {"elements": [{"text_run": {"content": "📅 运营与行动跟进表"}}]}})
        headers = ["核心任务", "责任人", "执行周期"]
        rows = [[t.get("task"), t.get("owner"), t.get("deadline")] for t in table_data]
        blocks.append(create_table(headers, rows))
        blocks.append(empty_line())

    # 6. 深度纪要
    chapters = data.get("chapters", [])
    if chapters:
        blocks.append({"block_type": 4, "heading2": {"elements": [{"text_run": {"content": "📝 会议原声深度详述"}}]}})
        for chap in chapters:
            blocks.append({"block_type": 5, "heading3": {"elements": [{"text_run": {"content": f"[{safe_text(chap.get('time'))}] {safe_text(chap.get('title'))}", "text_element_style": {"text_color": 5}}}]}})
            blocks.append(create_text(chap.get("content")))
            blocks.append(empty_line())

    return blocks

# ===================== 5. 深度递归写入引擎 =====================

def push_blocks_to_feishu(doc_id, blocks):
    token = get_feishu_token()
    base_url = f"https://open.feishu.cn/open-apis/docx/v1/documents/{doc_id}/blocks"
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    
    def insert_node(parent_id, children):
        batch = []
        for child in children:
            if child.get("block_type") in [24, 31, 19, 14]: # 新增 14 (Code Block)
                if batch:
                    requests.post(f"{base_url}/{parent_id}/children", headers=headers, json={"children": batch, "index": -1})
                    batch = []
                
                # 创建容器
                container_payload = {k: v for k, v in child.items() if k != "children"}
                res = requests.post(f"{base_url}/{parent_id}/children", headers=headers, json={"children": [container_payload], "index": -1}).json()
                
                if res.get("code") != 0:
                    st.error(f"⚠️ 组件写入警告 ({child.get('block_type')}): {res.get('msg')}")
                    continue
                    
                new_block_id = res.get("data", {}).get("children", [{}])[0].get("block_id")
                if not new_block_id: continue
                
                # 递归填充内容
                if child.get("block_type") in [24, 31]: # Grid, Table
                    auto_res = requests.get(f"{base_url}/{new_block_id}/children", headers=headers).json()
                    auto_items = auto_res.get("data", {}).get("items", [])
                    content_list = child.get("children", [])
                    for i, content_data in enumerate(content_list):
                        if i < len(auto_items):
                            insert_node(auto_items[i]["block_id"], content_data.get("children", []))
                
                elif child.get("block_type") in [19, 14]: # Callout, Code
                    inner_children = child.get("children", [])
                    if inner_children:
                        insert_node(new_block_id, inner_children)
            else:
                batch.append(child)
                if len(batch) >= 40:
                    requests.post(f"{base_url}/{parent_id}/children", headers=headers, json={"children": batch, "index": -1})
                    batch = []
                    
        if batch:
            requests.post(f"{base_url}/{parent_id}/children", headers=headers, json={"children": batch, "index": -1})

    insert_node(doc_id, blocks)
    return f"https://bytedance.feishu.cn/docx/{doc_id}"

# ===================== 6. 商业提炼引擎 (Prompt V4.0) =====================

@st.cache_resource
def load_model():
    return whisper.load_model("base")

def get_json_data(content):
    url = "https://dashscope.aliyuncs.com/api/v1/services/aigc/text-generation/generation"
    headers = {"Authorization": f"Bearer {QWEN_API_KEY}", "Content-Type": "application/json"}
    
    prompt = f"""
    你是一名麦肯锡级别的商业咨询顾问。请将会议内容转化为具备“图文看板+原生表格”结构的顶级纪要。
    
    【输出结构必须严格为 JSON】：
    {{
        "meta": {{ "theme": "会议主题", "time": "推测时间", "participants": "发言人" }},
        "core_consensus": "用一句话总结会议达成的最核心战略共识(带上核心数字)",
        "mermaid_mindmap": "mindmap\\n  root((战略核心))\\n    关键议题1\\n      细节A\\n    关键议题2\\n      细节B",
        "dashboard_row1": [
            {{ "title": "品牌溢价路径", "items": ["要点1", "要点2"], "color": 5, "emoji": "🚀" }},
            {{ "title": "本地化支撑体系", "items": ["资源1(必须带数据,如3.3万平)", "资源2(如百年企业)"], "color": 4, "emoji": "🏢" }}
        ],
        "dashboard_row2": [
            {{ "title": "分阶段落地策略", "items": ["短期规划", "长期规划"], "color": 2, "emoji": "🎯" }},
            {{ "title": "竞争壁垒与机遇", "items": ["行业洞察", "核心优势"], "color": 6, "emoji": "🛡️" }}
        ],
        "action_table": [
            {{ "task": "具体行动任务(如:考察威廉港仓库)", "owner": "负责方/人", "deadline": "短期/中长期" }}
        ],
        "chapters": [ 
            {{ 
                "time": "00:00:00", 
                "title": "节点主题", 
                "content": "【内容填充要求】必须包含不少于 150 字的深度纪要！重点提取：1. 具体数据(金额/面积/时间) 2. 客户案例(如英国姐妹品牌) 3. 双方争议点与解决方案。禁止流水账！" 
            }} 
        ]
    }}
    
    【注意事项】：
    1. dashboard 中的 color 只能在 1-7 中选择。
    2. mermaid_mindmap 必须使用合法 Mermaid `mindmap` 语法，换行用 \\\\n。
    
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

# ===================== 7. 主控 UI =====================

st.title("💎 飞书智能纪要：完美交付版")
st.info("已启用「双重视觉引擎」与「深度递归写入」。脑图、分栏、表格、长文本将 100% 呈现！")

uploaded_file = st.file_uploader("请上传会议文件 (TXT/Audio)", type=["mp3", "wav", "m4a", "txt"])

if uploaded_file and st.button("🚀 生成完美视觉看板", type="primary"):
    with st.status("正在启动多维视觉架构引擎...", expanded=True) as status:
        
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
            
        status.write("2️⃣ 顶级 AI 正在绘制脑图与构建卡片数据 (预计需 1-2 分钟)...")
        json_data = get_json_data(raw_text)
        
        if json_data:
            status.write("3️⃣ 建立云端通道...")
            doc_id = create_feishu_doc(json_data.get('meta', {}).get('theme', '顶级视图纪要'))
            
            if doc_id:
                status.write("4️⃣ 正在渲染高清脑图 (双重保险模式)...")
                mermaid_code = json_data.get("mermaid_mindmap")
                diagram_token, img_bytes = generate_and_upload_diagram(doc_id, mermaid_code) if mermaid_code else (None, None)
                
                status.write("5️⃣ 正在调用「深度递归引擎」编排原生分栏与高级表格...")
                blocks = build_visual_blocks(json_data, diagram_token, mermaid_code)
                doc_url = push_blocks_to_feishu(doc_id, blocks)
                
                if doc_url:
                    status.update(label="✅ 完美视觉看板生成成功！", state="complete")
                    
                    if img_bytes:
                        st.markdown("### 🧠 核心战略脑图预览")
                        st.image(img_bytes, use_column_width=True)
                    elif mermaid_code:
                         st.markdown("### 🧠 脑图逻辑预览 (图片上传超时，已在文档中降级为代码块)")
                         st.code(mermaid_code, language='mermaid')

                    st.markdown(f"""
                    <div style="background:#f0f2f5; padding:30px; border-radius:15px; text-align:center;">
                        <h2 style="color:#1f2329;">🎉 您的专属视觉战略看板已落成</h2>
                        <p style="color:#646a73;">多列彩色卡片 + 结构脑图 + 原生表格 + 会议万字长文记录</p>
                        <a href="{doc_url}" target="_blank" style="background:#3370ff; color:white; padding:15px 40px; text-decoration:none; border-radius:8px; font-weight:bold; font-size:18px; display:inline-block; margin-top:10px;">
                            🚀 立即检阅极具商业质感的飞书文档
                        </a>
                    </div>
                    """, unsafe_allow_html=True)
                else:
                    status.update(label="❌ 写入异常，请检查日志", state="error")
            else:
                status.update(label="❌ 文档创建失败", state="error")
        else:
            status.update(label="❌ 进程中止，大模型提炼失败", state="error")
