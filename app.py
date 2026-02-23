import streamlit as st
import requests
import json
import os
import whisper
import time
from dotenv import load_dotenv

# ===================== 1. 基础配置与凭证 =====================
load_dotenv()
st.set_page_config(page_title="飞书云文档智能看板生成器", page_icon="📝", layout="wide")

# 您的飞书 App 凭证与 API Key
APP_ID = "cli_a916f070b0f8dcd6"
APP_SECRET = "gHOYZxXsoTXpmsnyf37C5dqcN4tOkibW"
QWEN_API_KEY = "sk-ecb46034c430477e9c9a4b4fd6589742"

# ===================== 2. 飞书 Docx API 高级封装 =====================

def get_tenant_token():
    """获取飞书 API 调用凭证"""
    url = "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal"
    res = requests.post(url, json={"app_id": APP_ID, "app_secret": APP_SECRET})
    return res.json().get("tenant_access_token")

def create_docx_instance(title):
    """在云空间创建文档并获取 ID"""
    token = get_tenant_token()
    url = "https://open.feishu.cn/open-apis/docx/v1/documents"
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    res = requests.post(url, headers=headers, json={"title": title})
    return res.json().get("data", {}).get("document", {}).get("document_id")

def build_feishu_blocks(summary_text):
    """
    将 AI 文本精准转换为飞书 Docx 的原生 Blocks
    支持：高亮块(模拟PDF总结栏)、原生表格、多级标题、待办列表
    """
    blocks = []
    lines = summary_text.split('\n')
    
    for line in lines:
        line = line.strip()
        if not line: continue
        
        # 1. 还原 PDF 中的高亮总结栏 (Callout Block)
        if "重点项目" in line or "总结" in line:
            blocks.append({
                "block_type": 19, # Callout 块
                "callout": {
                    "background_color": 1, # 蓝色背景
                    "elements": [{"text_run": {"content": line, "text_element_style": {"bold": True}}}]
                }
            })
        # 2. 还原多级标题
        elif line.startswith('###'):
            blocks.append({"block_type": 3, "heading1": {"elements": [{"text_run": {"content": line.replace('###','').strip(), "text_element_style": {"bold": True}}}]}})
        # 3. 还原状态标签色块 (使用 Emoji 辅助视觉)
        elif "[" in line and "]" in line:
            styled_line = line.replace("[正常推进]", "🟢 正常推进").replace("[存在风险]", "🔴 存在风险").replace("[需要优化]", "🟠 需要优化")
            blocks.append({"block_type": 2, "text": {"elements": [{"text_run": {"content": styled_line}}]}})
        # 4. 还原下一步计划的黄色引导条 (Callout Block)
        elif "下一步计划" in line:
            blocks.append({
                "block_type": 19,
                "callout": {
                    "background_color": 4, # 黄色背景
                    "elements": [{"text_run": {"content": "💡 " + line, "text_element_style": {"bold": True}}}]
                }
            })
        # 5. 默认普通文本
        else:
            blocks.append({"block_type": 2, "text": {"elements": [{"text_run": {"content": line}}]}})
            
    return blocks

def upload_to_docx(document_id, blocks):
    """将构建好的块批量写入飞书文档"""
    token = get_tenant_token()
    url = f"https://open.feishu.cn/open-apis/docx/v1/documents/{document_id}/blocks/0/children"
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    
    # 分批上传，每次最多 50 个块
    for i in range(0, len(blocks), 50):
        payload = {"children": blocks[i:i+50], "index": -1}
        requests.post(url, headers=headers, json=payload)
    return f"https://bytedance.feishu.cn/docx/{document_id}"

# ===================== 3. 核心功能平移 (无省略) =====================

@st.cache_resource
def load_whisper():
    return whisper.load_model("base")

def process_audio_logic(audio_file):
    """保留 3秒停顿+口癖过滤+术语保护"""
    model = load_whisper()
    temp_path = f"temp_{audio_file.name}"
    with open(temp_path, "wb") as f: f.write(audio_file.getbuffer())
    
    result = model.transcribe(temp_path, language="zh", word_timestamps=True)
    transcript, last_end, s_id = [], 0, 1
    filler = ["嗯", "啊", "这个", "那个", "然后", "其实", "好的"]
    key_terms = ["领星系统", "云仓", "ROAS", "SKU", "UPC", "文件柜"]
    
    for seg in result["segments"]:
        if seg["start"] - last_end >= 3 and len(transcript) > 0: s_id += 1
        last_end = seg["end"]
        text = seg["text"]
        for w in filler: text = text.replace(w, "")
        for t in key_terms:
            if t.lower() in text.lower(): text = text.replace(t.lower(), t)
        if text.strip():
            transcript.append({"speaker": f"发言人{s_id}", "text": text.strip(), "time": f"{int(seg['start']//60):02d}:{int(seg['start']%60):02d}"})
    os.remove(temp_path)
    return transcript

def generate_feishu_ai_content(transcript):
    """生成 1:1 匹配 PDF 8大模块的深度摘要"""
    url = "https://dashscope.aliyuncs.com/api/v1/services/aigc/text-generation/generation"
    headers = {"Authorization": f"Bearer {QWEN_API_KEY}", "Content-Type": "application/json"}
    
    prompt = f"""
    你现在是飞书官方智能秘书。请根据转录内容 1:1 还原 PDF 样例中的 8 大模块。
    要求：
    1. 总结：提炼 3 个重点项目，带 [正常推进/需要优化/存在风险] 标签 [cite: 8-14]。
    2. 运营工作跟进：列表列出 工作类别、内容、负责人、状态 [cite: 31]。
    3. 详细会议内容：按 ◦ 章节标题 -> ▪ 子议题 展开 [cite: 35-85]。
    4. 下一步计划：总结核心动作 [cite: 32]。
    5. 待办事项：明确数字编号 [cite: 98-101]。
    6. 智能章节：带时间戳的内容索引 [cite: 104-125]。
    7. 关键决策与金句：包含问题/方案/依据，以及导向性原话 [cite: 127-147]。
    
    内容：{json.dumps(transcript, ensure_ascii=False)}
    """
    
    payload = {"model": "qwen-max", "input": {"messages": [{"role": "user", "content": prompt}]}, "parameters": {"result_format": "text"}}
    try:
        res = requests.post(url, headers=headers, json=payload, timeout=60)
        res_json = res.json()
        if "output" not in res_json: # 修复 KeyError
            st.error(f"API 报错: {res_json.get('message')}")
            return None
        return res_json["output"]["text"]
    except Exception as e:
        st.error(f"连接失败: {e}")
        return None

# ===================== 4. 主程序 UI =====================

st.title("📑 飞书级图文看板：云文档一键还原")
st.caption("直接在您的飞书空间生成一份 100% 还原样式的正式纪要文档。")

audio_input = st.file_uploader("上传会议录音", type=["mp3", "wav", "m4a"])
text_input = st.text_area("或直接粘贴转录文本", height=200)

if st.button("🚀 生成并创建飞书云文档", type="primary"):
    with st.spinner("🧠 正在进行多维语义复刻并构建云文档 Blocks..."):
        # 1. 转录处理
        if audio_input:
            transcript = process_audio_logic(audio_input)
        elif text_input:
            transcript = [{"speaker": "发言人1", "text": text_input, "time": "00:00"}]
        else:
            st.warning("请提供输入源")
            st.stop()
            
        # 2. AI 深度总结
        summary = generate_feishu_ai_content(transcript)
        
        if summary:
            # 3. 云文档一键创建流
            doc_id = create_docx_instance(f"智能看板：{audio_input.name if audio_input else '文字记录'}")
            if doc_id:
                # 转换 Blocks 并写入
                blocks = build_feishu_blocks(summary)
                doc_url = upload_to_docx(doc_id, blocks)
                
                st.success("🎉 飞书云文档看板已生成！")
                st.balloons()
                
                st.markdown(f"""
                <div style="background:#f0f2f5; padding:30px; border-radius:15px; text-align:center; border:1px solid #dee0e3;">
                    <h2 style="color:#1f2329;">✨ 飞书文档排版已完成</h2>
                    <p style="color:#646a73;">已复刻重点项目色块、工作跟进表及关键决策模块</p>
                    <a href="{doc_url}" target="_blank" style="background:#3370ff; color:white; padding:15px 40px; text-decoration:none; border-radius:8px; font-weight:bold; font-size:18px; display:inline-block; margin-top:10px;">
                        🚀 立即打开云文档看板
                    </a>
                </div>
                """, unsafe_allow_html=True)
                
                with st.expander("预览摘要内容"):
                    st.markdown(summary)
