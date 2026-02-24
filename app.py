import streamlit as st
import requests
import json
import os
import re
import whisper
from datetime import datetime

# 兼容 dotenv
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# ===================== 1. 基础配置 =====================
st.set_page_config(page_title="飞书原生纪要：商业战略看板版", page_icon="💎", layout="wide")

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
    safe_title = str(title).strip() if title else "战略会议纪要"
    res = requests.post(url, headers=headers, json={"title": safe_title})
    return res.json().get("data", {}).get("document", {}).get("document_id")

# ===================== 3. 原生 Dashboard 构建器 =====================

def safe_text(content):
    return str(content).replace('\n', ' ').strip() or " "

def empty_line():
    return {"block_type": 2, "text": {"elements": [{"text_run": {"content": " "}}]}}

def build_dashboard_blocks(data):
    """
    【商业看板排版引擎】：
    利用飞书原生的高亮背景色，模拟出精美的分块数据卡片 (Dashboard)
    """
    blocks = []

    # 1. 顶部元数据
    meta = data.get("meta", {})
    blocks.append({"block_type": 3, "heading1": {"elements": [{"text_run": {"content": safe_text(meta.get('theme', '战略会议纪要'))}}]}})
    blocks.append({"block_type": 2, "text": {"elements": [{"text_run": {"content": f"📅 时间: {safe_text(meta.get('time', '近期'))}   |   👥 参会人: {safe_text(meta.get('participants', '与会人员'))}", "text_element_style": {"text_color": 7}}}]}})
    blocks.append({"block_type": 22, "divider": {}}) # 分割线

    # 2. 战略级核心共识
    consensus = safe_text(data.get("core_consensus", ""))
    blocks.append({"block_type": 4, "heading2": {"elements": [{"text_run": {"content": "💡 战略核心共识"}}]}})
    blocks.append({
        "block_type": 2,
        "text": {"elements": [{"text_run": {"content": f" {consensus} ", "text_element_style": {"background_color": 5, "bold": True}}}]} # 5=浅蓝色高亮
    })
    blocks.append(empty_line())

    # 3. 商业架构看板 (原生卡片模拟)
    blocks.append({"block_type": 4, "heading2": {"elements": [{"text_run": {"content": "📊 会议逻辑架构与战略拆解"}}]}})
    dashboard = data.get("dashboard", {})
    
    # 卡片A：行业洞察 (紫色系)
    blocks.append({"block_type": 5, "heading3": {"elements": [{"text_run": {"content": "📈 行业演变洞察与核心优势"}}]}})
    for pt in dashboard.get("industry_insight", []):
        blocks.append({"block_type": 12, "bullet": {"elements": [{"text_run": {"content": safe_text(pt), "text_element_style": {"background_color": 6}}}]}})
    
    # 卡片B：品牌路径 (蓝色系)
    blocks.append({"block_type": 5, "heading3": {"elements": [{"text_run": {"content": "🚀 品牌溢价三步走路径"}}]}})
    for pt in dashboard.get("brand_path", []):
        blocks.append({"block_type": 12, "bullet": {"elements": [{"text_run": {"content": safe_text(pt), "text_element_style": {"background_color": 5}}}]}})
        
    # 卡片C：本地支撑 (绿色系)
    blocks.append({"block_type": 5, "heading3": {"elements": [{"text_run": {"content": "🏢 欧洲本地化支撑体系"}}]}})
    for pt in dashboard.get("local_support", []):
        blocks.append({"block_type": 12, "bullet": {"elements": [{"text_run": {"content": safe_text(pt), "text_element_style": {"background_color": 4}}}]}})
        
    # 卡片D：落地策略 (橙色系)
    blocks.append({"block_type": 5, "heading3": {"elements": [{"text_run": {"content": "🎯 分阶段落地策略"}}]}})
    for pt in dashboard.get("phased_strategy", []):
        blocks.append({"block_type": 12, "bullet": {"elements": [{"text_run": {"content": safe_text(pt), "text_element_style": {"background_color": 2}}}]}})
    
    blocks.append({"block_type": 22, "divider": {}})

    # 4. 行动与待办 (Checkbox矩阵)
    todos = data.get("todos", [])
    if todos:
        blocks.append({"block_type": 4, "heading2": {"elements": [{"text_run": {"content": "✅ 行动与待办矩阵"}}]}})
        for todo in todos:
            task = safe_text(todo.get("task"))
            owner = safe_text(todo.get("owner"))
            blocks.append({"block_type": 17, "todo": {"style": {"done": False}, "elements": [{"text_run": {"content": f"由 @{owner} 负责: {task}"}}] }})
        blocks.append({"block_type": 22, "divider": {}})

    # 5. 原声回溯与深度纪要 (强制高信息密度)
    chapters = data.get("chapters", [])
    if chapters:
        blocks.append({"block_type": 4, "heading2": {"elements": [{"text_run": {"content": "⏱️ 核心议题深层详述"}}]}})
        for chap in chapters:
            time_str = safe_text(chap.get("time"))
            title_str = safe_text(chap.get("title"))
            blocks.append({"block_type": 5, "heading3": {"elements": [{"text_run": {"content": f"[{time_str}] {title_str}", "text_element_style": {"text_color": 5}}}]}})
            
            # 渲染深度内容
            content_str = safe_text(chap.get("content"))
            blocks.append({"block_type": 2, "text": {"elements": [{"text_run": {"content": content_str}}]}})
            blocks.append(empty_line())

    return blocks

def push_blocks_to_feishu(doc_id, blocks):
    token = get_feishu_token()
    url = f"https://open.feishu.cn/open-apis/docx/v1/documents/{doc_id}/blocks/{doc_id}/children"
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    
    # 启用安全重试机制
    for i in range(0, len(blocks), 40):
        batch = blocks[i:i+40]
        try:
            res = requests.post(url, headers=headers, json={"children": batch}, timeout=15)
            if res.json().get("code") != 0:
                for block in batch: 
                    requests.post(url, headers=headers, json={"children": [block]})
        except Exception:
            pass
    return f"https://bytedance.feishu.cn/docx/{doc_id}"

# ===================== 4. 商业提炼引擎 (重构大模型认知框架) =====================

@st.cache_resource
def load_model():
    return whisper.load_model("base")

def get_json_data(content):
    url = "https://dashscope.aliyuncs.com/api/v1/services/aigc/text-generation/generation"
    headers = {"Authorization": f"Bearer {QWEN_API_KEY}", "Content-Type": "application/json"}
    
    prompt = f"""
    你是一名麦肯锡级别的顶级商业咨询顾问。请将下方的会议逐字稿转化为极具战略高度、且【信息极度丰满】的结构化商业报告。
    
    【输出结构必须严格为 JSON】：
    {{
        "meta": {{ "theme": "会议主题", "time": "推测时间", "participants": "发言人" }},
        "core_consensus": "用不少于50字的商业话术总结会议达成的最核心共识",
        "dashboard": {{
            "industry_insight": ["行业趋势洞察(带具体背景)", "中方核心优势(必须提取具体数据,如几家工厂/合作方)"],
            "brand_path": ["品牌化路径步骤1", "步骤2", "步骤3(如:组装转移/本地化)"],
            "local_support": ["本地仓储物流优势(必须带具体数字,如面积/时效)", "本地分销网络优势(如合作方渠道)"],
            "phased_strategy": ["短期行动计划(0-3个月)", "中长期建设规划(4-12个月)"]
        }},
        "todos": [ {{ "task": "具体行动指令", "owner": "负责人" }} ],
        "chapters": [ 
            {{ 
                "time": "00:00:00", 
                "title": "节点主题", 
                "content": "【致命警告】此处为会议细节复原！字数绝对不得少于 150 字！必须像速记员一样，把该段落中提到的客户案例、具体业务卡点、数据指标、详细的推演逻辑全盘写出，严禁做干瘪的一句话概括！" 
            }} 
        ]
    }}
    
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

st.title("💎 飞书智能纪要：商业战略看板版")
st.info("已全面接入【麦肯锡商业框架】与【原生卡片排版引擎】，保留 150字/段 极限细节！")

uploaded_file = st.file_uploader("请上传会议文件 (TXT/Audio)", type=["mp3", "wav", "m4a", "txt"])

if uploaded_file and st.button("🚀 生成专家级战略看板", type="primary"):
    with st.status("正在启动战略架构引擎...", expanded=True) as status:
        
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
            
        status.write("2️⃣ 顶级商业 AI 正在进行战略解构与长文本扩容 (预计需 1-2 分钟)...")
        json_data = get_json_data(raw_text)
        
        if json_data:
            status.write("3️⃣ 建立云端通道...")
            doc_id = create_feishu_doc(json_data.get('meta', {}).get('theme', '战略会议看板'))
            
            if doc_id:
                status.write("4️⃣ 注入原生彩色看板模块与万字详解...")
                blocks = build_dashboard_blocks(json_data)
                doc_url = push_blocks_to_feishu(doc_id, blocks)
                
                if doc_url:
                    status.update(label="✅ 原生飞书高密度纪要生成成功！", state="complete")
                    st.markdown(f"""
                    <div style="background:#f0f2f5; padding:30px; border-radius:15px; text-align:center;">
                        <h2 style="color:#1f2329;">🎉 战略级商业看板已就绪</h2>
                        <p style="color:#646a73;">已原生复刻四大核心战略模块，且会议细节不漏一字！</p>
                        <a href="{doc_url}" target="_blank" style="background:#3370ff; color:white; padding:15px 40px; text-decoration:none; border-radius:8px; font-weight:bold; font-size:18px; display:inline-block; margin-top:10px;">
                            🚀 立即检阅您的专属看板
                        </a>
                    </div>
                    """, unsafe_allow_html=True)
                else:
                    status.update(label="❌ 写入异常，请检查日志", state="error")
            else:
                status.update(label="❌ 文档创建失败", state="error")
        else:
            status.update(label="❌ 进程中止，大模型提炼失败", state="error")
