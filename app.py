# -*- coding: utf-8 -*-
"""
飞书原生智能纪要工具（极简版：一键创建飞书文档）
无需机器人，直接在飞书里看
"""
import streamlit as st
import os
from modules.feishu_api import create_feishu_smart_notes
from modules.preprocess import parse_speech

# 页面配置
st.set_page_config(
    page_title="飞书原生智能纪要工具",
    page_icon="📝",
    layout="wide"
)
st.title("📝 飞书原生智能纪要工具")
st.subheader("上传会议文本，一键生成飞书原生智能纪要", divider="blue")

# 侧边栏：模板选择
st.sidebar.title("⚙️ 配置")
template_type = st.sidebar.selectbox(
    "选择会议模板",
    options=["通用商务会议", "项目同步会议", "需求评审会议", "周度例会"],
    index=0
)

# 主界面：上传会议文本
uploaded_file = st.file_uploader("上传会议文本（TXT格式）", type=["txt"])
if uploaded_file is not None:
    try:
        meeting_text = uploaded_file.read().decode("utf-8")
        st.success("✅ 文件上传成功！")
        
        # 预览原始文本
        with st.expander("📄 查看原始会议记录", expanded=False):
            st.text(meeting_text)
        
        # 一键生成飞书原生纪要
        if st.button("🚀 一键生成飞书原生智能纪要", type="primary"):
            with st.spinner("🔍 正在生成飞书原生智能纪要..."):
                # 核心：直接创建飞书原生文档
                doc_title = f"{template_type}_飞书原生智能纪要"
                feishu_doc = create_feishu_smart_notes(doc_title, meeting_text, template_type)
                
                # 显示飞书文档链接
                st.success(f"✅ 飞书原生智能纪要生成完成！")
                st.markdown(f"🔗 **飞书文档链接**：[点击查看]({feishu_doc['doc_url']})")
                st.info("直接在飞书里打开链接，就是完整的飞书原生智能纪要！")
                
                # 预览飞书原生内容（可选）
                with st.expander("📋 预览飞书原生内容", expanded=False):
                    from modules.extract import extract_meeting_info
                    from modules.template import fill_template, load_all_templates
                    
                    speech_list = parse_speech(meeting_text)
                    extract_result = extract_meeting_info(speech_list, template_type)
                    templates = load_all_templates()
                    summary_text = fill_template(extract_result, templates[template_type])
                    st.markdown(summary_text, unsafe_allow_html=True)
    except Exception as e:
        st.error(f"❌ 生成失败：{str(e)}")
