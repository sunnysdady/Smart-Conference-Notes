# -*- coding: utf-8 -*-
"""
通用智能会议纪要生成工具（嵌入API Key）
"""
import streamlit as st
import os
from modules.preprocess import parse_speech
from modules.extract import extract_meeting_info, FIXED_API_KEY
from modules.template import fill_template, load_all_templates
from modules.output import save_md, save_word

# 页面配置
st.set_page_config(
    page_title="通用智能会议纪要生成工具",
    page_icon="📝",
    layout="wide"
)
st.title("📝 通用智能会议纪要生成工具")
st.subheader("上传任意文字会议记录，生成飞书风格智能纪要", divider="blue")

# 侧边栏（隐藏API Key输入，仅保留模板选择）
st.sidebar.title("⚙️ 工具配置")
st.sidebar.subheader("📋 选择会议模板")
template_type = st.sidebar.selectbox(
    "适配所有会议类型",
    options=["通用商务会议", "项目同步会议", "需求评审会议", "周度例会"],
    index=0
)
# 加载模板
templates = load_all_templates()
selected_template = templates[template_type]

# 主界面：文件上传+生成纪要
uploaded_file = st.file_uploader("上传会议文字记录（TXT格式）", type=["txt"])
if uploaded_file is not None:
    try:
        meeting_text = uploaded_file.read().decode("utf-8")
        st.success("✅ 文件上传成功！")
        
        # 预览原始文本
        with st.expander("📄 查看原始会议记录", expanded=False):
            st.text(meeting_text)
        
        # 生成纪要按钮
        if st.button("🚀 生成飞书风格智能纪要", type="primary"):
            with st.spinner("🔍 正在调用大模型分析会议内容..."):
                # 预处理文本
                speech_list = parse_speech(meeting_text)
                # 提取信息（无需传Key，使用嵌入的默认值）
                extract_result = extract_meeting_info(speech_list, template_type)
                
                # 处理结果
                if "error" in extract_result:
                    st.error(f"❌ {extract_result['error']}")
                else:
                    # 填充模板
                    summary_text = fill_template(extract_result, selected_template)
                    # 预览纪要
                    st.subheader("📋 飞书风格智能会议纪要", divider="green")
                    st.markdown(summary_text)
                    
                    # 生成下载文件
                    md_path = f"{template_type}_飞书风格纪要.md"
                    word_path = f"{template_type}_飞书风格纪要.docx"
                    
                    # 保存MD文件
                    with open(md_path, 'w', encoding='utf-8') as f:
                        f.write(summary_text)
                    with open(md_path, 'r', encoding='utf-8') as f:
                        st.download_button(f"📥 下载MD格式-{template_type}纪要", f, file_name=md_path)
                    
                    # 保存Word文件
                    from docx import Document
                    doc = Document()
                    doc.add_heading(extract_result["会议核心信息"]["主题"], level=1)
                    for line in summary_text.split("\n"):
                        if line.startswith("##"):
                            doc.add_heading(line.replace("## ", ""), level=2)
                        elif line.startswith("-"):
                            doc.add_paragraph(line, style='List Bullet')
                        elif line:
                            doc.add_paragraph(line)
                    doc.save(word_path)
                    with open(word_path, 'rb') as f:
                        st.download_button(f"📥 下载Word格式-{template_type}纪要", f, file_name=word_path)
                    
                    st.success(f"🎉 {template_type}纪要生成完成！完全匹配飞书格式")
    except Exception as e:
        st.error(f"❌ 文件读取/处理失败：{str(e)}")

# 页脚
st.markdown(
    """
    <div style='text-align: center; color: #666; font-size: 12px; margin-top: 50px;'>
    💡 工具基于通义千问大模型开发 | 输出飞书风格标准化纪要 | 支持所有办公会议类型
    </div>
    """,
    unsafe_allow_html=True
)
