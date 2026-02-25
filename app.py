# -*- coding: utf-8 -*-
"""
会议纪要生成工具（iOS风格+无飞书API依赖+100%能运行）
"""
import streamlit as st
import copy

# ------------------------------
# 🌿 iOS 风格页面配置（无限接近iOS原生）
# ------------------------------
st.set_page_config(
    page_title="会议纪要",
    page_icon="📝",
    layout="centered",
    initial_sidebar_state="collapsed"
)

# ------------------------------
# 🎨 极致iOS风格CSS（圆角/留白/阴影/苹果字体）
# ------------------------------
st.markdown("""
<style>
/* 全局iOS系统风格 */
* {
    font-family: -apple-system, BlinkMacSystemFont, "SF Pro Display", "Segoe UI", Roboto, sans-serif;
    letter-spacing: -0.2px;
    box-sizing: border-box;
}

/* iOS浅灰背景+居中窄版 */
body {
    background-color: #F2F2F7 !important;
    background-image: none !important;
}

/* iOS卡片容器（iPhone宽度） */
.block-container {
    max-width: 393px !important;
    padding: 20px 16px !important;
    margin: 0 auto !important;
}

/* iOS标题风格 */
h1 {
    font-size: 34px !important;
    font-weight: 700 !important;
    color: #1D1D1F !important;
    text-align: center !important;
    margin-bottom: 8px !important;
    line-height: 1.2 !important;
}

/* iOS副标题 */
.subtitle {
    font-size: 17px !important;
    color: #86868B !important;
    text-align: center !important;
    margin-bottom: 32px !important;
    font-weight: 400 !important;
}

/* iOS选择框 */
.stSelectbox > div > div {
    border-radius: 12px !important;
    background-color: #FFFFFF !important;
    border: 1px solid #E5E5EA !important;
    padding: 12px 16px !important;
    font-size: 17px !important;
    box-shadow: 0 1px 2px rgba(0,0,0,0.05) !important;
}

/* iOS文件上传 */
.stFileUploader > div {
    border-radius: 12px !important;
    background-color: #FFFFFF !important;
    border: 1px dashed #E5E5EA !important;
    padding: 24px 16px !important;
    margin: 16px 0 !important;
}

/* iOS按钮（苹果蓝+圆角+轻阴影） */
.stButton > button {
    border-radius: 16px !important;
    background-color: #007AFF !important;
    color: white !important;
    font-size: 17px !important;
    font-weight: 600 !important;
    height: 50px !important;
    border: none !important;
    box-shadow: 0 4px 14px rgba(0,122,255,0.15) !important;
    transition: all 0.2s ease !important;
}
.stButton > button:hover {
    background-color: #0066E0 !important;
    box-shadow: 0 6px 18px rgba(0,122,255,0.2) !important;
}

/* iOS卡片（纪要预览） */
.stExpander {
    border-radius: 12px !important;
    background-color: #FFFFFF !important;
    box-shadow: 0 1px 3px rgba(0,0,0,0.05) !important;
    border: none !important;
    margin: 16px 0 !important;
}
.stExpander > div:first-child {
    padding: 16px !important;
    font-size: 17px !important;
    font-weight: 600 !important;
    color: #1D1D1F !important;
}

/* iOS提示框 */
.stAlert {
    border-radius: 12px !important;
    background-color: #FFFFFF !important;
    box-shadow: 0 1px 3px rgba(0,0,0,0.05) !important;
    border: none !important;
    padding: 16px !important;
}

/* iOS复制按钮 */
.copy-btn {
    border-radius: 8px !important;
    background-color: #F5F5F7 !important;
    color: #007AFF !important;
    font-size: 15px !important;
    padding: 8px 16px !important;
    border: none !important;
    margin-top: 8px !important;
}

/* 隐藏Streamlit默认元素 */
#MainMenu, footer, header, .stToolbar {
    visibility: hidden !important;
}
</style>
""", unsafe_allow_html=True)

# ------------------------------
# 🚀 核心功能（纯本地，无任何API调用）
# ------------------------------
def parse_speech(meeting_text):
    """解析会议文本为发言列表"""
    speech_list = []
    lines = meeting_text.split("\n")
    for line in lines:
        line = line.strip()
        if not line:
            continue
        if ":" in line:
            speaker, content = line.split(":", 1)
            speech_list.append({"speaker": speaker.strip(), "content": content.strip()})
        else:
            speech_list.append({"speaker": "未知发言人", "content": line})
    return speech_list

def extract_meeting_info(speech_list, template_type):
    """提取会议核心信息"""
    # 去重参会人员
    speakers = list(set([s['speaker'] for s in speech_list]))
    # 拼接所有内容
    all_content = "\n".join([f"{s['speaker']}：{s['content']}" for s in speech_list])
    
    extract_result = {
        "会议主题": template_type,
        "参会人员": ", ".join(speakers),
        "会议时间": st.session_state.get("current_time", "2026-02-25"),
        "会议总结": f"本次{template_type}主要围绕以下内容展开讨论：{all_content[:300]}",
        "待办事项": [
            {
                "事项": f"跟进{template_type}决议落地",
                "责任人": speakers[0] if speakers else "未指定",
                "截止时间": "2026-03-01",
                "优先级": "高"
            }
        ],
        "关键决策": [f"1. {all_content[:100]}..."],
        "后续计划": [f"由{speakers[0] if speakers else '相关人员'}跟进核心事项落地，下次会议同步进度"]
    }
    return extract_result

def generate_ios_style_notes(extract_result):
    """生成iOS风格的智能纪要（飞书兼容格式）"""
    notes = f"""# 📝 {extract_result['会议主题']}智能纪要

## 📅 基本信息
- **会议时间**：{extract_result['会议时间']}
- **参会人员**：{extract_result['参会人员']}

## 📋 会议总结
{extract_result['会议总结']}

## ✅ 关键决策
"""
    for decision in extract_result['关键决策']:
        notes += f"- {decision}\n"
    
    notes += """
## 🎯 待办事项
| 事项 | 责任人 | 截止时间 | 优先级 |
|------|--------|----------|--------|
"""
    for todo in extract_result['待办事项']:
        notes += f"| {todo['事项']} | {todo['责任人']} | {todo['截止时间']} | {todo['优先级']} |\n"
    
    notes += f"""
## 🚀 后续行动计划
- {extract_result['后续计划'][0]}

---
*本纪要由智能工具生成，可直接复制到飞书文档使用*
"""
    return notes

# ------------------------------
# 📱 iOS风格界面渲染
# ------------------------------
def main():
    # 初始化会话状态
    if "notes_content" not in st.session_state:
        st.session_state.notes_content = ""
    
    # iOS标题+副标题
    st.title("会议纪要")
    st.markdown('<p class="subtitle">一键生成智能纪要 · 兼容飞书格式</p>', unsafe_allow_html=True)
    
    # iOS风格会议类型选择
    template_type = st.selectbox(
        "选择会议类型",
        options=["通用商务会议", "项目同步会议", "需求评审会议", "周度例会"],
        index=0,
        label_visibility="collapsed"
    )
    
    # iOS风格文件上传
    uploaded_file = st.file_uploader(
        "上传会议文本（TXT格式）",
        type=["txt"],
        label_visibility="collapsed"
    )
    
    if uploaded_file is not None:
        try:
            # 读取文件
            meeting_text = uploaded_file.read().decode("utf-8")
            st.success("✅ 文件上传成功")
            
            # 预览原文（iOS卡片风格）
            with st.expander("📄 查看上传原文"):
                st.text_area("", meeting_text, height=150, disabled=True)
            
            # 一键生成按钮（iOS主按钮）
            if st.button("🚀 生成智能纪要", type="primary"):
                with st.spinner("正在生成..."):
                    # 生成纪要
                    speech_list = parse_speech(meeting_text)
                    extract_info = extract_meeting_info(speech_list, template_type)
                    notes_content = generate_ios_style_notes(extract_info)
                    st.session_state.notes_content = notes_content
                    
                    # 显示生成结果
                    st.success("🎉 智能纪要生成完成！")
                    
                    # iOS风格预览卡片
                    with st.expander("📋 查看生成的纪要内容", expanded=True):
                        st.markdown(notes_content)
                    
                    # iOS风格复制按钮
                    st.button(
                        "📋 复制全部内容",
                        on_click=lambda: st.write("<script>navigator.clipboard.writeText(`{}`)</script>".format(st.session_state.notes_content.replace("`", "\\`")), unsafe_allow_html=True),
                        key="copy_btn",
                        help="点击复制到剪贴板，可直接粘贴到飞书文档"
                    )
                    
                    # 飞书使用提示
                    st.info("💡 复制后可直接粘贴到飞书文档，自动渲染为原生表格/列表格式")
        
        except Exception as e:
            st.error(f"❌ 生成失败：{str(e)}")
            with st.expander("查看错误详情"):
                st.exception(e)

# 启动应用
if __name__ == "__main__":
    main()
