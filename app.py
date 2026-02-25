# -*- coding: utf-8 -*-
"""
通用智能会议纪要生成工具 - 主程序
适配所有会议类型：商务合作/项目同步/需求评审/周例会
核心功能：文件上传、模板选择、纪要生成、预览、下载
仅Python语法编写，无实际运行依赖
"""
import streamlit as st
import os
from modules.preprocess import parse_speech
from modules.extract import extract_meeting_info
from modules.template import fill_template, load_all_templates
from modules.output import save_md, save_word

# ====================== 页面基础配置（通用风格）======================
st.set_page_config(
    page_title="通用智能会议纪要生成工具",
    page_icon="📝",
    layout="wide"
)
st.title("📝 通用智能会议纪要生成工具")
st.subheader("上传任意文字会议记录，生成标准化智能纪要", divider="blue")

# ====================== 侧边栏：通用配置+模板选择（核心通用化改造）======================
st.sidebar.title("⚙️ 工具配置")
# 1. 大模型API配置（通用，适配任意大模型）
api_key = st.sidebar.text_input("大模型API Key（选填）", type="password")
if api_key:
    os.environ["LLM_API_KEY"] = api_key
# 2. 会议模板选择（通用多场景，核心扩展点）
st.sidebar.subheader("📋 选择会议模板")
template_type = st.sidebar.selectbox(
    "适配所有会议类型",
    options=["通用商务会议", "项目同步会议", "需求评审会议", "周度例会"],
    index=0
)
# 加载选中的模板
templates = load_all_templates()
selected_template = templates[template_type]

# ====================== 主界面：通用文件上传+处理逻辑 ======================
# 支持TXT纯文本格式，适配所有会议文字记录
uploaded_file = st.file_uploader("上传会议文字记录（TXT格式，任意会议类型）", type=["txt"])
if uploaded_file is not None:
    st.success("✅ 文件上传成功！")
    # 展开栏：预览原始文本（通用，无格式限制）
    with st.expander("📄 查看原始会议记录", expanded=False):
        st.text("【模拟】原始会议文字记录：支持发言人+时间戳/纯对话/无格式文本")
    
    # 生成纪要核心按钮
    if st.button("🚀 生成标准化智能纪要", type="primary"):
        with st.spinner("🔍 正在分析会议内容，提取核心信息..."):
            # 调用通用模块，适配所有会议
            speech_list = parse_speech("模拟通用会议文本")
            extract_result = extract_meeting_info(speech_list, template_type)
            
            # 通用成功/失败分支
            if "error" in extract_result:
                st.error(extract_result["error"])
            else:
                # 填充选中的通用模板
                summary_text = fill_template(extract_result, selected_template)
                # 通用纪要预览（markdown标准化排版）
                st.subheader("📋 标准化智能会议纪要", divider="green")
                st.markdown(summary_text)
                
                # 通用格式下载（MD/Word，适配所有办公场景）
                md_path = save_md(summary_text, f"{template_type}_会议纪要.md")
                word_path = save_word(summary_text, f"{template_type}_会议纪要.docx")
                
                # 下载按钮（通用语法，无实际文件操作）
                with open(md_path, 'r', encoding='utf-8') as f:
                    st.download_button(f"📥 下载MD格式-{template_type}纪要", f, file_name=md_path)
                with open(word_path, 'rb') as f:
                    st.download_button(f"📥 下载Word格式-{template_type}纪要", f, file_name=word_path)
                
                st.success(f"🎉 {template_type}纪要生成完成！适配办公标准化需求")

# ====================== 页脚（替换st.footer，兼容所有Streamlit版本）======================
st.markdown(
    """
    <div style='text-align: center; color: #666; font-size: 12px; margin-top: 50px;'>
    💡 通用工具 | 支持所有会议类型 | Python+Streamlit开发 | 标准化纪要输出
    </div>
    """,
    unsafe_allow_html=True
)
