import streamlit as st
import requests
import json
import os
import re
import whisper
from datetime import datetime
from dotenv import load_dotenv

# ===================== 1. 基础配置 =====================
load_dotenv()
st.set_page_config(page_title="飞书原生会议纪要-1:1复刻版", page_icon="💎", layout="wide")

APP_ID = "cli_a916f070b0f8dcd6"
APP_SECRET = "gHOYZxXsoTXpmsnyf37C5dqcN4tOkibW"
QWEN_API_KEY = "sk-ecb46034c430477e9c9a4b4fd6589742"

# ===================== 2. 飞书底层 API 封装 =====================

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
    safe_title = str(title).strip() if title else "智能会议纪要"
    res = requests.post(url, headers=headers, json={"title": safe_title})
    return res.json().get("data", {}).get("document", {}).get("document_id")

def build_feishu_native_blocks(data):
    """
    【1:1 原版排版引擎】
    完美复刻飞书原生智能纪要的“元数据 -> 核心提炼 -> 待办 -> 章节”四大模块。
    """
    blocks = []
    
    def safe_text(content):
        return str(content).replace('\n', ' ').strip() or " "

    # --- 模块 1：顶部元数据 (Meta Info) ---
    blocks.append({"block_type": 3, "heading1": {"elements": [{"text_run": {"content": "纪要"}}]}})
    meta = data.get("meta", {})
    blocks.append({"block_type": 2, "text": {"elements": [{"text_run": {"content": f"主题: {safe_text(meta.get('theme', '会议纪要'))}", "text_element_style": {"text_color": 7}}}]}})
    blocks.append({"block_type": 2, "text": {"elements": [{"text_run": {"content": f"时间: {safe_text(meta.get('time', datetime.now().strftime('%Y-%m-%d %H:%M:%S')))}", "text_element_style": {"text_color": 7}}}]}})
    blocks.append({"block_type": 2, "text": {"elements": [{"text_run": {"content": f"参与人: {safe_text(meta.get('participants', '与会人员'))}", "text_element_style": {"text_color": 7}}}]}})
    blocks.append({"block_type": 22, "divider": {}}) # 分割线

    # --- 模块 2：核心战略提炼 (Executive Summary) ---
    exec_sum = data.get("executive_summary", {})
    blocks.append({"block_type": 3, "heading1": {"elements": [{"text_run": {"content": safe_text(exec_sum.get("title", "核心战略布局"))}}]}})
    
    subtitle = safe_text(exec_sum.get("subtitle", ""))
    if subtitle.strip() and subtitle != " ":
        # 使用浅蓝色 Callout 模拟高亮总结
        blocks.append({
            "block_type": 19,
            "callout": {
                "background_color": 5, 
                "elements": [{"text_run": {"content": subtitle, "text_element_style": {"bold": True}}}]
            }
        })

    for pillar in exec_sum.get("pillars", []):
        blocks.append({"block_type": 4, "heading2": {"elements": [{"text_run": {"content": safe_text(pillar.get("name"))}}]}})
        for point in pillar.get("points", []):
            blocks.append({"block_type": 12, "bullet": {"elements": [{"text_run": {"content": safe_text(point)}}]}})
    blocks.append({"block_type": 22, "divider": {}})

    # --- 模块 3：待办事项 (To-Dos) ---
    todos = data.get("todos", [])
    if todos:
        blocks.append({"block_type": 3, "heading1": {"elements": [{"text_run": {"content": "✅ 待办"}}]}})
        for todo in todos:
            task = safe_text(todo.get("task"))
            owner = safe_text(todo.get("owner"))
            # 启用飞书原生的 Todo Checkbox 组件
            blocks.append({
                "block_type": 14,
                "todo": {
                    "elements": [{"text_run": {"content": f"{task} (@{owner})"}}]
                }
            })
        blocks.append({"block_type": 22, "divider": {}})

    # --- 模块 4：智能章节 (Smart Chapters) ---
    chapters = data.get("chapters", [])
    if chapters:
        blocks.append({"block_type": 3, "heading1": {"elements": [{"text_run": {"content": "⏱️ 章节"}}]}})
        for chap in chapters:
            time_str = safe_text(chap.get("time"))
            title_str = safe_text(chap.get("title"))
            # 使用 Heading 3 并加上主题色，模拟原版时间戳标题
            blocks.append({
                "block_type": 5,
                "heading3": {"elements": [{"text_run": {"content": f"{time_str} {title_str}", "text_element_style": {"text_color": 5}}}]}
            })
            # 章节摘要内容
            blocks.append({
                "block_type": 2,
                "text": {"elements": [{"text_run": {"content": safe_text(chap.get("summary"))}}]}
            })

    return blocks

def push_blocks_to_feishu(doc_id, blocks):
    token = get_feishu_token()
    url = f"https://open.feishu.cn/open-apis/docx/v1/documents/{doc_id}/blocks/{doc_id}/children"
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    
    for i in range(0, len(blocks), 40):
        batch = blocks[i:i+40]
        try:
            res = requests.post(url, headers=headers, json={"children": batch}, timeout=15)
            data = res.json()
            if data.get("code") != 0:
                st.error(f"❌ 写入被拦截: {data.get('msg')}")
                st.write("故障节点:", batch[0])
                return None
        except Exception as e:
            st.error(f"❌ 网络传输中断: {e}")
            return None
    return f"https://bytedance.feishu.cn/docx/{doc_id}"

# ===================== 3. 商业咨询级 AI 引擎 =====================

@st.cache_resource
def load_model():
    return whisper.load_model("base")

def get_json_data(content):
    url = "https://dashscope.aliyuncs.com/api/v1/services/aigc/text-generation/generation"
    headers = {"Authorization": f"Bearer {QWEN_API_KEY}", "Content-Type": "application/json"}
    
    prompt = f"""
    你现在是顶级的商业战略顾问和飞书智能秘书。请阅读下方的会议逐字稿，并将其进行“战略升维”提炼，输出为严格的 JSON 格式。
    
    【输出结构必须如下，不可擅自更改】：
    {{
        "meta": {{
            "theme": "会议的主题(如: 中德钢制家具本土化合作)",
            "time": "提取或推测的会议时间",
            "participants": "发言人姓名或代号(用逗号隔开)"
        }},
        "executive_summary": {{
            "title": "高度提炼的战略标题(如: 中德钢制家具欧洲本土化布局)",
            "subtitle": "用一句话总结本次会议的核心目的",
            "pillars": [
                {{
                    "name": "提炼的战略维度(如: 品牌溢价路径 / 本地化支撑体系 / 分阶段落地策略 / 竞争壁垒与市场机遇)",
                    "points": ["战略要点1(需包含具体数据或行动)", "战略要点2"]
                }}
            ]
        }},
        "todos": [
            {{ "task": "具体的行动指令", "owner": "负责人姓名或代号" }}
        ],
        "chapters": [
            {{ "time": "00:00:00 (提取对应的时间戳)", "title": "该段落的核心议题", "summary": "该段落的详细总结(不少于50字)" }}
        ]
    }}
    
    【特别注意】：
    1. executive_summary 部分不要只是简单罗列谁说了什么，要像咨询报告一样提炼出“商业模式”、“落地策略”和“竞争优势”。
    2. chapters 部分需要根据文本中的时间戳（如 00:03:08）对会议进行切片总结。
    
    原文内容：{content[:25000]}
    """
    try:
        res = requests.post(url, headers=headers, json={"model": "qwen-max", "input": {"messages": [{"role": "user", "content": prompt}]}}, timeout=90)
        text = res.json()["output"]["text"]
        match = re.search(r'\{.*\}', text, re.DOTALL)
        if match: return json.loads(match.group(0))
        return None
    except Exception as e:
        st.error(f"AI 解析失败: {e}")
        return None

# ===================== 4. 主控 UI =====================

st.title("💎 飞书原生会议纪要：1:1 完美复刻版")
st.info("已全面升级 AI 战略提炼引擎，启用原生 Checkbox 待办与时间戳智能章节组件。")

uploaded_file = st.file_uploader("请上传录音或逐字稿 (TXT)", type=["mp3", "wav", "m4a", "txt"])

if uploaded_file and st.button("🚀 生成专家级云文档", type="primary"):
    with st.status("正在启动战略升维引擎...", expanded=True) as status:
        
        status.write("1️⃣ 解析输入文件...")
        if uploaded_file.name.endswith('.txt'):
            raw_text = uploaded_file.read().decode("utf-8")
        else:
            status.write("调用 Whisper 提取带时间戳的逐字稿 (请稍作等待)...")
            model = load_model()
            temp_path = f"temp_{uploaded_file.name}"
            with open(temp_path, "wb") as f: f.write(uploaded_file.getbuffer())
            
            # 使用 whisper 获取带时间戳的文本，以供 AI 划分章节
            result = model.transcribe(temp_path, language="zh")
            raw_text = ""
            for seg in result["segments"]:
                minutes = int(seg['start'] // 60)
                seconds = int(seg['start'] % 60)
                raw_text += f"[{minutes:02d}:{seconds:02d}] {seg['text']}\n"
            os.remove(temp_path)
            
        status.write("2️⃣ 顶级商业顾问 AI 正在提炼战略框架...")
        json_data = get_json_data(raw_text)
        
        if json_data:
            status.write("3️⃣ 建立云端通道...")
            doc_id = create_feishu_doc(json_data.get('meta', {}).get('theme', '专家级会议纪要'))
            
            if doc_id:
                status.write("4️⃣ 注入原生 Checkbox 与章节排版...")
                blocks = build_feishu_native_blocks(json_data)
                doc_url = push_blocks_to_feishu(doc_id, blocks)
                
                if doc_url:
                    status.update(label="✅ 原生飞书文档写入成功！", state="complete")
                    st.markdown(f"""
                    <div style="background:#f0f2f5; padding:30px; border-radius:15px; text-align:center;">
                        <h2 style="color:#1f2329;">🎉 战略级智能纪要已生成</h2>
                        <p style="color:#646a73;">已完美复刻「智能章节」与「待办矩阵」</p>
                        <a href="{doc_url}" target="_blank" style="background:#3370ff; color:white; padding:15px 40px; text-decoration:none; border-radius:8px; font-weight:bold; font-size:18px; display:inline-block; margin-top:10px;">
                            🚀 立即检阅您的专属纪要
                        </a>
                    </div>
                    """, unsafe_allow_html=True)
                else:
                    status.update(label="❌ 写入遭遇拦截", state="error")
            else:
                status.update(label="❌ 文档创建失败", state="error")
        else:
            status.update(label="❌ AI 提炼异常", state="error")
