import streamlit as st
import requests
import json
import os
import re
import whisper
import base64
import zlib
from datetime import datetime

# 兼容 dotenv
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# ===================== 1. 基础配置 =====================
st.set_page_config(page_title="飞书原生纪要：图文架构版", page_icon="📈", layout="wide")

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
    safe_title = str(title).strip() if title else "智能图文纪要"
    res = requests.post(url, headers=headers, json={"title": safe_title})
    return res.json().get("data", {}).get("document", {}).get("document_id")

def upload_diagram_to_feishu(mermaid_code):
    """将 Mermaid 代码渲染成图片并上传至飞书"""
    token = get_feishu_token()
    if not token or not mermaid_code or len(mermaid_code) < 10: return None
    
    try:
        clean_code = mermaid_code.replace("```mermaid", "").replace("```", "").strip()
        compressed = zlib.compress(clean_code.encode('utf-8'), 9)
        encoded = base64.urlsafe_b64encode(compressed).decode('ascii')
        img_url = f"https://kroki.io/mermaid/png/{encoded}"
        
        img_res = requests.get(img_url, timeout=20)
        if img_res.status_code != 200: return None
        img_bytes = img_res.content

        upload_url = "https://open.feishu.cn/open-apis/drive/v1/medias/upload_all"
        headers = {"Authorization": f"Bearer {token}"}
        data = {"file_name": "diagram.png", "parent_type": "docx_image", "size": len(img_bytes)}
        files = {"file": ("diagram.png", img_bytes, "image/png")}
        
        up_res = requests.post(upload_url, headers=headers, data=data, files=files, timeout=15)
        return up_res.json().get("data", {}).get("file_token")
    except Exception as e:
        st.warning(f"图形渲染失败，跳过图表插入: {e}")
        return None

# ===================== 3. 通用万能排版与安全构建器 =====================

def safe_text(content):
    return str(content).replace('\n', ' ').strip() or " "

def empty_line():
    return {"block_type": 2, "text": {"elements": [{"text_run": {"content": " "}}]}}

def build_universal_blocks(data, diagram_file_token=None):
    blocks = []

    meta = data.get("meta", {})
    blocks.append({"block_type": 3, "heading1": {"elements": [{"text_run": {"content": safe_text(meta.get('theme', '智能纪要'))}}]}})
    blocks.append({"block_type": 2, "text": {"elements": [{"text_run": {"content": f"📅 {safe_text(meta.get('time', '近期'))}  |  👥 {safe_text(meta.get('participants', '与会人员'))}", "text_element_style": {"text_color": 7}}}]}})
    blocks.append(empty_line())

    summary = data.get("quick_summary", [])
    if summary:
        blocks.append({"block_type": 4, "heading2": {"elements": [{"text_run": {"content": "💡 一分钟速读 (核心共识)"}}]}})
        for point in summary:
            blocks.append({
                "block_type": 2,
                "text": {"elements": [{"text_run": {"content": f" {safe_text(point)} ", "text_element_style": {"background_color": 5, "bold": True}}}]}
            })
        blocks.append(empty_line())

    if diagram_file_token:
        blocks.append({"block_type": 4, "heading2": {"elements": [{"text_run": {"content": "📊 会议逻辑架构图"}}]}})
        blocks.append({"block_type": 27, "image": {"token": diagram_file_token}})
        blocks.append(empty_line())

    topics = data.get("topics", [])
    if topics:
        blocks.append({"block_type": 4, "heading2": {"elements": [{"text_run": {"content": "📝 核心议题详述"}}]}})
        for idx, topic in enumerate(topics):
            blocks.append({"block_type": 5, "heading3": {"elements": [{"text_run": {"content": f"{idx+1}. {safe_text(topic.get('title'))}", "text_element_style": {"text_color": 5}}}]}})
            for detail in topic.get("details", []):
                blocks.append({"block_type": 12, "bullet": {"elements": [{"text_run": {"content": safe_text(detail)}}]}})
            conclusion = safe_text(topic.get("conclusion", ""))
            if conclusion and conclusion != " ":
                blocks.append({"block_type": 2, "text": {"elements": [{"text_run": {"content": f" ➔ 结论: {conclusion} ", "text_element_style": {"bold": True, "text_color": 4}}}]}})
            blocks.append(empty_line())

    todos = data.get("todos", [])
    if todos:
        blocks.append({"block_type": 4, "heading2": {"elements": [{"text_run": {"content": "✅ 行动与待办"}}]}})
        for todo in todos:
            task = safe_text(todo.get("task"))
            owner = safe_text(todo.get("owner"))
            blocks.append({"block_type": 17, "todo": {"style": {"done": False}, "elements": [{"text_run": {"content": f"{task} (@{owner})"}}] }})
        blocks.append(empty_line())

    chapters = data.get("chapters", [])
    if chapters:
        blocks.append({"block_type": 4, "heading2": {"elements": [{"text_run": {"content": "⏱️ 智能章节"}}]}})
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
                for block in batch:
                    requests.post(url, headers=headers, json={"children": [block]})
        except Exception:
            pass
    return f"https://bytedance.feishu.cn/docx/{doc_id}"

# ===================== 4. 【核心修复】可视化显性报错引擎 =====================

@st.cache_resource
def load_model():
    return whisper.load_model("base")

def get_json_data(content):
    url = "https://dashscope.aliyuncs.com/api/v1/services/aigc/text-generation/generation"
    headers = {"Authorization": f"Bearer {QWEN_API_KEY}", "Content-Type": "application/json"}
    
    prompt = f"""
    你现在是商业咨询顾问。请分析会议逐字稿，提取出深层信息，并严格输出 JSON 格式。
    
    【输出结构必须如下】：
    {{
        "meta": {{
            "theme": "会议主题",
            "time": "推测的时间",
            "participants": "发言人"
        }},
        "quick_summary": [
            "用一句话总结会议达成的第1个核心共识",
            "用一句话总结会议达成的第2个核心共识"
        ],
        "mermaid_code": "graph TD\\\\nA[核心] --> B(议题)\\\\nB --> C{{结论}}",
        "topics": [
            {{
                "title": "议题名称",
                "details": ["细节1", "细节2"],
                "conclusion": "该议题得出的结论"
            }}
        ],
        "todos": [
            {{ "task": "具体行动指令", "owner": "负责人" }}
        ],
        "chapters": [
            {{ "time": "00:00:00", "title": "节点主题", "summary": "简要说明" }}
        ]
    }}
    
    【致命警告】：
    1. mermaid_code 字段中的换行，必须使用双反斜杠加n (即 \\\\n ) 代替！绝不允许直接在此 JSON 字符串中按回车换行！
    2. details 必须包含具体业务数据和案例。
    
    原文内容：{content[:25000]}
    """
    
    try:
        # 1. 扩容超时限制至 180 秒
        res = requests.post(url, headers=headers, json={"model": "qwen-max", "input": {"messages": [{"role": "user", "content": prompt}]}}, timeout=180)
        res_data = res.json()
        
        # 2. 拦截 API 报错
        if "output" not in res_data:
            st.error(f"❌ 阿里云 API 返回异常: {res_data.get('message', res_data)}")
            return None
            
        text = res_data["output"]["text"]
        match = re.search(r'\{.*\}', text, re.DOTALL)
        
        if match:
            raw_json_str = match.group(0)
            try:
                # 3. 拦截 JSON 解析报错，并开启非严格模式
                return json.loads(raw_json_str, strict=False)
            except json.JSONDecodeError as e:
                st.error(f"❌ 大模型输出的 JSON 格式非法 (通常是因为 Mermaid 代码中含有未转义的换行符或引号): {e}")
                with st.expander("点击查看大模型返回的错误数据"):
                    st.code(raw_json_str)
                return None
        else:
            st.error("❌ 大模型未输出 JSON 格式的数据。")
            return None
            
    except requests.exceptions.Timeout:
        st.error("❌ 请求超时！大模型处理长文本并生成图表代码的时间超过了 180 秒。")
        return None
    except Exception as e:
        st.error(f"❌ 发生未知网络错误: {e}")
        return None

# ===================== 5. 主控 UI =====================

st.title("📈 飞书智能纪要：图文架构通杀版")
st.info("已全面接入底层报错穿透系统与超时扩容引擎，让错误无所遁形！")

uploaded_file = st.file_uploader("请上传会议文件 (TXT/Audio)", type=["mp3", "wav", "m4a", "txt"])

if uploaded_file and st.button("🚀 生成万能图文纪要", type="primary"):
    with st.status("正在启动图文架构引擎...", expanded=True) as status:
        
        status.write("1️⃣ 解析输入文件...")
        if uploaded_file.name.endswith('.txt'):
            raw_text = uploaded_file.read().decode("utf-8")
        else:
            status.write("正在提取带时间戳的语音切片...")
            model = load_model()
            temp_path = f"temp_{uploaded_file.name}"
            with open(temp_path, "wb") as f: f.write(uploaded_file.getbuffer())
            
            result = model.transcribe(temp_path, language="zh")
            raw_text = ""
            for seg in result["segments"]:
                raw_text += f"[{int(seg['start']//60):02d}:{int(seg['start']%60):02d}] {seg['text']}\n"
            os.remove(temp_path)
            
        status.write("2️⃣ AI 正在进行议题下钻与逻辑架构提炼 (可能需要 1-2 分钟)...")
        json_data = get_json_data(raw_text)
        
        if json_data:
            status.write("3️⃣ 建立云端通道...")
            doc_id = create_feishu_doc(json_data.get('meta', {}).get('theme', '万能图文纪要'))
            
            if doc_id:
                status.write("4️⃣ 正在渲染高清架构图片并上传飞书媒体库...")
                mermaid_code = json_data.get("mermaid_code")
                diagram_token = upload_diagram_to_feishu(mermaid_code) if mermaid_code else None
                if diagram_token:
                    status.write("✔️ 架构图渲染成功，已成功挂载！")
                
                status.write("5️⃣ 注入通用安全排版与原声切片...")
                blocks = build_universal_blocks(json_data, diagram_token)
                doc_url = push_blocks_to_feishu(doc_id, blocks)
                
                if doc_url:
                    status.update(label="✅ 原生飞书图文纪要生成成功！", state="complete")
                    st.markdown(f"""
                    <div style="background:#f0f2f5; padding:30px; border-radius:15px; text-align:center;">
                        <h2 style="color:#1f2329;">🎉 您的专属图文看板已就绪</h2>
                        <a href="{doc_url}" target="_blank" style="background:#3370ff; color:white; padding:15px 40px; text-decoration:none; border-radius:8px; font-weight:bold; font-size:18px; display:inline-block; margin-top:10px;">
                            🚀 立即检阅震撼的排版效果
                        </a>
                    </div>
                    """, unsafe_allow_html=True)
                else:
                    status.update(label="❌ 写入异常，请检查日志", state="error")
            else:
                status.update(label="❌ 文档创建失败", state="error")
        else:
            status.update(label="❌ 进程中止，请查看上方红色报错提示", state="error")
