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
st.set_page_config(page_title="飞书原生看板-绝对安全版", page_icon="🎯", layout="wide")

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
    safe_title = str(title).strip() if title else "智能会议看板"
    res = requests.post(url, headers=headers, json={"title": safe_title})
    return res.json().get("data", {}).get("document", {}).get("document_id")

def build_100pct_safe_blocks(data):
    """
    【终极防线引擎】
    修复了您的 JSON 日志中指出的两个核心报错点：
    1. 颜色 ID 严格限制在官方合法的 1-7 之间。
    2. 消灭 "\n"，统一使用 " " 占位。
    """
    blocks = []
    
    # 清洗函数：绝不允许出现空字符串或孤立的换行符
    def safe_text(content):
        c = str(content).replace('\n', ' ').strip() if content else ""
        return c if c else " " 

    # 1. 标题与基础信息
    blocks.append({"block_type": 3, "heading1": {"elements": [{"text_run": {"content": safe_text(data.get("title", "智能纪要"))}}]}})
    blocks.append({"block_type": 2, "text": {"elements": [{"text_run": {"content": f"📅 {safe_text(data.get('date', '近期'))} | AI智能提取", "text_element_style": {"text_color": 7}}}]}})
    blocks.append({"block_type": 2, "text": {"elements": [{"text_run": {"content": " "}}]}}) # 安全的空行占位

    # 2. 重点项目
    blocks.append({"block_type": 4, "heading2": {"elements": [{"text_run": {"content": "📊 重点项目概览"}}]}})
    for proj in data.get("projects", []):
        status = safe_text(proj.get("status", "进行中"))
        name = safe_text(proj.get("name", "未命名项目"))
        
        # 官方绝对安全色号: 1=红, 2=橙, 3=黄, 4=绿, 5=蓝, 6=紫, 7=灰
        tc, bgc = 5, 7 # 默认蓝字灰底
        if "正常" in status or "完成" in status: tc, bgc = 4, 4
        elif "风险" in status or "滞销" in status or "待" in status: tc, bgc = 1, 1
        elif "优化" in status: tc, bgc = 2, 2
            
        blocks.append({
            "block_type": 2,
            "text": {"elements": [
                {"text_run": {"content": f" ❖ {name}   ", "text_element_style": {"bold": True}}},
                {"text_run": {"content": f" {status} ", "text_element_style": {"text_color": tc, "background_color": bgc, "bold": True}}}
            ]}
        })
        for detail in proj.get("details", []):
            blocks.append({"block_type": 12, "bullet": {"elements": [{"text_run": {"content": safe_text(detail)}}]}})
    blocks.append({"block_type": 2, "text": {"elements": [{"text_run": {"content": " "}}]}})

    # 3. 运营工作
    blocks.append({"block_type": 4, "heading2": {"elements": [{"text_run": {"content": "🗓️ 运营工作跟进"}}]}})
    for op in data.get("operations", []):
        status = safe_text(op.get("status", "待定"))
        tc, bgc = (4,4) if "完成" in status else ((1,1) if "待" in status else (2,2))
        
        blocks.append({
            "block_type": 12,
            "bullet": {"elements": [
                {"text_run": {"content": f"{safe_text(op.get('category', '分类'))}   ", "text_element_style": {"bold": True}}},
                {"text_run": {"content": f" {status} ", "text_element_style": {"text_color": tc, "background_color": bgc, "bold": True}}},
                {"text_run": {"content": f"  |  操作: {safe_text(op.get('content', '无'))}  |  负责人: {safe_text(op.get('owner', '待定'))}", "text_element_style": {"text_color": 7}}}
            ]}
        })
    blocks.append({"block_type": 2, "text": {"elements": [{"text_run": {"content": " "}}]}})

    # 4. 下一步计划
    blocks.append({"block_type": 4, "heading2": {"elements": [{"text_run": {"content": "🚀 下一步计划"}}]}})
    blocks.append({
        "block_type": 2,
        "text": {"elements": [
            {"text_run": {"content": f" 💡 {safe_text(data.get('next_steps', '暂无'))} ", "text_element_style": {"bold": True, "background_color": 3}}} # 3=官方合法的黄色
        ]}
    })
    blocks.append({"block_type": 2, "text": {"elements": [{"text_run": {"content": " "}}]}})

    # 5. 核心决策
    blocks.append({"block_type": 4, "heading2": {"elements": [{"text_run": {"content": "🎯 核心决策"}}]}})
    for dec in data.get("decisions", []):
        prob = safe_text(dec.get('problem', '无'))
        sol = safe_text(dec.get('solution', '无'))
        blocks.append({
            "block_type": 12, 
            # 采用 ➔ 替代回车符 \n，防止解析断层
            "bullet": {"elements": [{"text_run": {"content": f"问题：{prob}  ➔  方案：{sol}"}}]}
        })

    return blocks

def push_blocks_to_feishu(doc_id, blocks):
    token = get_feishu_token()
    url = f"https://open.feishu.cn/open-apis/docx/v1/documents/{doc_id}/blocks/0/children"
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    
    for i in range(0, len(blocks), 40):
        batch = blocks[i:i+40]
        try:
            res = requests.post(url, headers=headers, json={"children": batch, "index": -1}, timeout=15)
            data = res.json()
            if data.get("code") != 0:
                st.error(f"❌ 区块写入被拦截: {data.get('msg')}")
                st.json(batch) 
                return None
        except Exception as e:
            st.error(f"❌ 网络传输中断: {e}")
            return None
    return f"https://bytedance.feishu.cn/docx/{doc_id}"

# ===================== 3. AI 解析核心 =====================

@st.cache_resource
def load_model():
    return whisper.load_model("base")

def get_json_data(content):
    url = "https://dashscope.aliyuncs.com/api/v1/services/aigc/text-generation/generation"
    headers = {"Authorization": f"Bearer {QWEN_API_KEY}", "Content-Type": "application/json"}
    
    prompt = f"""
    将以下会议内容转化为 JSON 格式。如果原文没有对应信息，请填入"未提及"或空数组[]，绝不允许省略字段。
    结构必须是：
    {{
        "title": "会议主题", "date": "XXXX年XX月XX日",
        "projects": [{{"name": "项目名", "status": "正常推进/存在风险/需要优化", "details": ["细节说明"]}}],
        "operations": [{{"category": "类别", "content": "内容", "owner": "负责人", "status": "状态"}}],
        "next_steps": "下一步整体计划",
        "decisions": [{{"problem": "问题", "solution": "方案"}}]
    }}
    原文：{content[:20000]}
    """
    try:
        res = requests.post(url, headers=headers, json={"model": "qwen-max", "input": {"messages": [{"role": "user", "content": prompt}]}}, timeout=60)
        text = res.json()["output"]["text"]
        match = re.search(r'\{.*\}', text, re.DOTALL)
        if match: return json.loads(match.group(0))
        return None
    except:
        return None

# ===================== 4. 主控 UI =====================

st.title("🛡️ 飞书原生看板：最后拼图版")
st.info("已全面清洗导致 invalid param 的越界色彩代码与非法换行，确保完美写入！")

uploaded_file = st.file_uploader("请上传音频或TXT", type=["mp3", "wav", "m4a", "txt"])

if uploaded_file and st.button("🚀 执行渲染生成", type="primary"):
    with st.status("正在启动安全护航引擎...", expanded=True) as status:
        
        status.write("1️⃣ 解析输入文件...")
        if uploaded_file.name.endswith('.txt'):
            raw_text = uploaded_file.read().decode("utf-8")
        else:
            status.write("调用 Whisper 本地转录 (稍作等待)...")
            model = load_model()
            temp_path = f"temp_{uploaded_file.name}"
            with open(temp_path, "wb") as f: f.write(uploaded_file.getbuffer())
            raw_text = model.transcribe(temp_path, language="zh")["text"]
            os.remove(temp_path)
            
        status.write("2️⃣ AI 结构化降维...")
        json_data = get_json_data(raw_text)
        
        if json_data:
            status.write("3️⃣ 建立云端通道...")
            doc_id = create_feishu_doc(json_data.get('title', '智能纪要看板'))
            
            if doc_id:
                status.write("4️⃣ 注入官方安全色彩与 Block 排版...")
                blocks = build_100pct_safe_blocks(json_data)
                doc_url = push_blocks_to_feishu(doc_id, blocks)
                
                if doc_url:
                    status.update(label="✅ 原生飞书文档写入成功！", state="complete")
                    st.markdown(f"""
                    <div style="background:#f0f2f5; padding:30px; border-radius:15px; text-align:center;">
                        <h2 style="color:#1f2329;">🎉 结构化看板已成功降落云端</h2>
                        <a href="{doc_url}" target="_blank" style="background:#3370ff; color:white; padding:15px 40px; text-decoration:none; border-radius:8px; font-weight:bold; font-size:18px; display:inline-block; margin-top:10px;">
                            🚀 立即检阅您的专属纪要
                        </a>
                    </div>
                    """, unsafe_allow_html=True)
                else:
                    status.update(label="❌ 写入遭遇拦截，请核对日志", state="error")
            else:
                status.update(label="❌ 文档创建失败", state="error")
        else:
            status.update(label="❌ AI 解析异常", state="error")
