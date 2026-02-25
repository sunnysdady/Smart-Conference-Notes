# -*- coding: utf-8 -*-
import streamlit as st
import os

# ------------------------------
# 🌿 iOS 风格页面配置
# ------------------------------
st.set_page_config(
    page_title="会议纪要",
    page_icon="📝",
    layout="centered",
    initial_sidebar_state="collapsed"
)

# ------------------------------
# 🎨 iOS 风格 CSS
# ------------------------------
st.markdown("""
<style>
* {
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", "Roboto", "Helvetica Neue", Arial, sans-serif;
    letter-spacing: 0.2px;
}
body {
    background-color: #F5F7FA;
}
.block-container {
    max-width: 390px !important;
    padding-top: 2rem !important;
    padding-bottom: 3rem !important;
}
h1 {
    font-size: 28px !important;
    font-weight: 600 !important;
    color: #1D1D1F !important;
    text-align: center !important;
    margin-bottom: 10px !important;
}
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
.uploadedFile {
    border-radius: 14px !important;
    background-color: white !important;
    box-shadow: 0 1px 3px rgba(0,0,0,0.05) !important;
}
.stAlert {
    border-radius: 12px !important;
    background-color: white !important;
    box-shadow: 0 1px 3px rgba(0,0,0,0.05) !important;
    border-left: none !important;
}
div.stExpander {
    border-radius: 14px !important;
    background-color: white !important;
    box-shadow: 0 1px 3px rgba(0,0,0,0.04) !important;
}
#MainMenu, footer, header {visibility: hidden;}
</style>
""", unsafe_allow_html=True)

# ------------------------------
# 📱 核心功能（延迟导入，避免错误）
# ------------------------------
def main():
    # 延迟导入feishu_api，避免启动时导入错误
    try:
        from modules.feishu_api import create_feishu_smart_notes
    except ImportError as e:
        st.error(f"❌ 核心模块导入失败：{str(e)}")
        st.stop()
    
    # 界面内容
    st.title("会议纪要")
    st.markdown(
        '<p style="text-align: center; color: #8A8A8E; margin-top:-10px; margin-bottom:30px;">'
        '一键生成飞书原生智能纪要</p>',
        unsafe_allow_html=True
    )
    
    # 模板选择
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
    
            # 预览原文
            with st.expander("查看原文", expanded=False):
                st.text(meeting_text)
    
            # 一键生成
            if st.button("🚀 生成飞书纪要", type="primary"):
                with st.spinner("处理中..."):
                    doc_title = f"{template_type}_智能纪要"
                    feishu_doc = create_feishu_smart_notes(doc_title, meeting_text, template_type)
    
                    # 显示结果
                    st.success("✅ 飞书纪要已生成")
                    st.markdown(f"🔗 **文档链接**：[点击打开]({feishu_doc['doc_url']})")
                    st.info("在飞书中打开，就是原生纪要格式！")
    
        except Exception as e:
            st.error(f"❌ 生成失败：{str(e)}")
            with st.expander("错误详情"):
                st.exception(e)

# 启动应用
if __name__ == "__main__":
    main()
