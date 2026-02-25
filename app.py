# -*- coding: utf-8 -*-
import streamlit as st
import os
from modules.feishu_api import create_feishu_smart_notes

# ------------------------------
# 🌿 iOS 风格页面配置（核心）
# ------------------------------
st.set_page_config(
    page_title="会议纪要",
    page_icon="📝",
    layout="centered",  # iOS 喜欢居中、窄版
    initial_sidebar_state="collapsed"
)

# ------------------------------
# 🎨 iOS 风格 CSS（圆角、卡片、字体、阴影）
# ------------------------------
st.markdown("""
<style>
/* 全局 iOS 风格 */
* {
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", "Roboto", "Helvetica Neue", Arial, sans-serif;
    letter-spacing: 0.2px;
}
body {
    background-color: #F5F7FA;
}
/* 主容器居中、窄版，像 iPhone 界面 */
.block-container {
    max-width: 390px !important;
    padding-top: 2rem !important;
    padding-bottom: 3rem !important;
}
/* 标题 iOS 风格 */
h1 {
    font-size: 28px !important;
    font-weight: 600 !important;
    color: #1D1D1F !important;
    text-align: center !important;
    margin-bottom: 10px !important;
}
/* 卡片：iOS 圆角卡片 */
div.stButton > button {
    border-radius: 14px !important;
    background-color: #007AFF !important;
    color: white !important;
    font-weight: 500 !important;
    border: none !important;
    height: 50px !important;
    font-size: 16px !important;
    box-shadow: 0 2px 8px rgba(0,122,255,0.15) !important;
}
div.stButton > button:hover {
    background-color: #0062CC !important;
    box-shadow: 0 3px 10px rgba(0,122,255,0.2) !important;
}
/* 上传区域 iOS 风格 */
.uploadedFile {
    border-radius: 14px !important;
    background-color: white !important;
    box-shadow: 0 1px 3px rgba(0,0,0,0.05) !important;
}
/* 卡片容器 */
div.element-container div {
    border-radius: 14px !important;
}
/* 成功/信息气泡 iOS 风格 */
.stAlert {
    border-radius: 12px !important;
    background-color: white !important;
    box-shadow: 0 1px 3px rgba(0,0,0,0.05) !important;
    border-left: none !important;
}
/* 收起面板 iOS 风格 */
div.stExpander {
    border-radius: 14px !important;
    background-color: white !important;
    box-shadow: 0 1px 3px rgba(0,0,0,0.04) !important;
}
/* 隐藏 Streamlit 自带元素 */
#MainMenu, footer, header {visibility: hidden;}
</style>
""", unsafe_allow_html=True)

# ------------------------------
# 📱 iOS 界面内容
# ------------------------------
st.title("会议纪要")

st.markdown(
    '<p style="text-align: center; color: #8A8A8E; margin-top:-10px; margin-bottom:30px;">'
    '一键生成飞书原生智能纪要</p>',
    unsafe_allow_html=True
)

# 模板选择（iOS 简洁下拉）
template_type = st.selectbox(
    "会议类型",
    options=["通用商务会议", "项目同步会议", "需求评审会议", "周度例会"],
    index=0
)

# 文件上传
uploaded_file = st.file_uploader("上传会议文本（TXT）", type=["txt"])

if uploaded_file is not None:
    try:
        meeting_text = uploaded_file.read().decode("utf-8")
        st.success("✅ 文件已上传")

        # 预览
        with st.expander("查看原文", expanded=False):
            st.text(meeting_text)

        # 一键生成（iOS 大按钮）
        if st.button("🚀 生成飞书纪要", type="primary"):
            with st.spinner("处理中..."):
                doc_title = f"{template_type}_智能纪要"
                feishu_doc = create_feishu_smart_notes(doc_title, meeting_text, template_type)

                st.success("✅ 飞书纪要已生成")
                st.markdown(f"🔗 **文档链接**：[点击打开]({feishu_doc['doc_url']})")
                st.info("在飞书中打开，就是原生纪要格式")

    except Exception as e:
        st.error(f"❌ 生成失败：{str(e)}")
        with st.expander("错误详情"):
            st.exception(e)
