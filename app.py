# -*- coding: utf-8 -*-
"""
通用智能会议纪要生成工具（飞书集成版）
"""
import streamlit as st
import os
from modules.preprocess import parse_speech
from modules.extract import extract_meeting_info
from modules.template import fill_template, load_all_templates
from modules.feishu_api import create_feishu_doc, send_feishu_robot_msg

# 页面配置
st.set_page_config(
    page_title="飞书风格智能会议纪要生成工具",
    page_icon="📝",
    layout="wide"
)
st.title("📝 飞书风格智能会议纪要生成工具")
st.subheader("上传任意文字会议记录，一键生成飞书原生风格纪要并同步到飞书文档", divider="blue")

# 侧边栏：模板选择
st.sidebar.title("⚙️ 工具配置")
st.sidebar.subheader("📋 选择会议模板")
template_type = st.sidebar.selectbox(
    "适配所有会议类型",
    options=["通用商务会议", "项目同步会议", "需求评审会议", "周度例会"],
    index=0
)
# 飞书同步开关
sync_to_feishu = st.sidebar.checkbox("生成后自动同步到飞书文档", value=True)
send_robot_msg = st.sidebar.checkbox("飞书机器人发送通知", value=True)

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
                # 1. 预处理文本
                speech_list = parse_speech(meeting_text)
                # 2. 提取飞书风格信息
                extract_result = extract_meeting_info(speech_list, template_type)
                
                # 3. 处理错误
                if "error" in extract_result:
                    st.error(f"❌ {extract_result['error']}")
                else:
                    # 4. 渲染飞书风格模板
                    summary_text = fill_template(extract_result, selected_template)
                    # 5. 预览纪要（飞书风格）
                    st.subheader("📋 飞书风格智能会议纪要", divider="green")
                    # 渲染HTML（模拟飞书高亮块）
                    st.markdown(summary_text, unsafe_allow_html=True)
                    
                    # 6. 生成MD下载文件
                    md_filename = f"{template_type}_飞书风格纪要.md"
                    with open(md_filename, 'w', encoding='utf-8') as f:
                        f.write(summary_text)
                    with open(md_filename, 'r', encoding='utf-8') as f:
                        st.download_button(f"📥 下载MD格式-{template_type}纪要", f, file_name=md_filename)
                    
                    # 7. 同步到飞书文档
                    if sync_to_feishu:
                        try:
                            with st.spinner("📤 正在同步到飞书文档..."):
                                doc_title = f"{extract_result['会议核心信息']['主题']}_{template_type}"
                                feishu_doc = create_feishu_doc(doc_title, summary_text)
                                st.success(f"✅ 飞书文档同步成功：[点击查看]({feishu_doc['doc_url']})")
                                
                                # 8. 飞书机器人通知
                                if send_robot_msg:
                                    send_success = send_feishu_robot_msg(doc_title, feishu_doc['doc_url'])
                                    if send_success:
                                        st.success("✅ 飞书机器人通知发送成功！")
                                    else:
                                        st.warning("⚠️ 飞书机器人通知发送失败（请检查webhook配置）")
                        except Exception as e:
                            st.warning(f"⚠️ 飞书文档同步失败：{str(e)}")
                    
                    st.success(f"🎉 {template_type}纪要生成完成！完全匹配飞书原生风格")
    except Exception as e:
        st.error(f"❌ 文件读取/处理失败：{str(e)}")

# 页脚
st.markdown(
    """
    <div style='text-align: center; color: #666; font-size: 12px; margin-top: 50px;'>
    💡 飞书风格智能会议纪要工具 | 通义千问大模型驱动 | 自动同步飞书文档
    </div>
    """,
    unsafe_allow_html=True
)
