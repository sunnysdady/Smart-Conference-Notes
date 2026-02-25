# -*- coding: utf-8 -*-
"""
飞书API模块（极简版：直接创建原生智能纪要文档）
"""
import requests
import json
from typing import Dict, Any

# ========== 你的飞书配置（直接填好） ==========
FEISHU_CONFIG = {
    "APP_ID": "cli_a916f070b0f8dcd6",
    "APP_SECRET": "gHOYZxXsoTXpmsnyf37C5dqcN4tOkibW",
    "TENANT_ACCESS_TOKEN": ""
}
# =============================================

def get_tenant_access_token() -> str:
    """获取飞书租户Token"""
    url = "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal"
    headers = {"Content-Type": "application/json"}
    data = {
        "app_id": FEISHU_CONFIG["APP_ID"],
        "app_secret": FEISHU_CONFIG["APP_SECRET"]
    }
    try:
        response = requests.post(url, headers=headers, json=data, timeout=30, verify=False)
        response.raise_for_status()
        result = response.json()
        if result.get("code") == 0:
            FEISHU_CONFIG["TENANT_ACCESS_TOKEN"] = result["tenant_access_token"]
            return result["tenant_access_token"]
        raise Exception(f"获取Token失败：{result.get('msg', '未知错误')}")
    except Exception as e:
        raise Exception(f"飞书API错误：{str(e)}")

def create_feishu_smart_notes(title: str, meeting_text: str, template_type: str = "通用商务会议") -> Dict[str, Any]:
    """
    一键创建飞书原生智能纪要文档（核心函数）
    :param title: 纪要标题
    :param meeting_text: 原始会议文本
    :param template_type: 会议模板类型
    :return: 飞书文档信息（含链接）
    """
    # 1. 调用通义千问生成飞书原生内容
    from modules.extract import extract_meeting_info
    from modules.preprocess import parse_speech
    from modules.template import fill_template, load_all_templates
    
    speech_list = parse_speech(meeting_text)
    extract_result = extract_meeting_info(speech_list, template_type)
    templates = load_all_templates()
    summary_text = fill_template(extract_result, templates[template_type])
    
    # 2. 获取飞书Token
    if not FEISHU_CONFIG["TENANT_ACCESS_TOKEN"]:
        get_tenant_access_token()
    
    # 3. 创建飞书文档（用 drive/v1/files 接口，解决 document_id 报错）
    create_url = "https://open.feishu.cn/open-apis/drive/v1/files/create"
    headers = {
        "Authorization": f"Bearer {FEISHU_CONFIG['TENANT_ACCESS_TOKEN']}",
        "Content-Type": "application/json"
    }
    create_data = {
        "title": title,
        "type": "docx",
        "folder_token": ""  # 可选：指定飞书文档文件夹
    }
    
    response = requests.post(create_url, headers=headers, json=create_data, timeout=30, verify=False)
    response.raise_for_status()
    create_result = response.json()
    
    if create_result.get("code") != 0:
        raise Exception(f"创建文档失败：{create_result.get('msg')}")
    
    file_token = create_result["data"]["file_token"]
    
    # 4. Markdown 转飞书原生节点（高亮标签、时间线、待办事项）
    def md_to_feishu_nodes(md_content: str) -> list:
        nodes = []
        lines = md_content.split("\n")
        for line in lines:
            line = line.strip()
            if not line:
                continue
            
            # 标题1
            if line.startswith("# "):
                nodes.append({
                    "type": "heading1",
                    "heading1": {"elements": [{"type": "textRun", "textRun": {"content": line[2:]}}]}
                })
            # 标题2
            elif line.startswith("## "):
                nodes.append({
                    "type": "heading2",
                    "heading2": {"elements": [{"type": "textRun", "textRun": {"content": line[2:]}}]}
                })
            # 飞书高亮标签块（原生样式）
            elif line.startswith("【") and "】" in line:
                tag_name, tag_content = line.split("】", 1)
                tag_name = tag_name[1:]
                nodes.append({
                    "type": "paragraph",
                    "paragraph": {
                        "style": {
                            "backgroundColor": "#f0f7ff",
                            "borderLeft": {"color": "#1890ff", "width": 4}
                        },
                        "elements": [
                            {"type": "textRun", "textRun": {"content": f"【{tag_name}】 ", "style": {"bold": True}}},
                            {"type": "textRun", "textRun": {"content": tag_content.strip()}}
                        ]
                    }
                })
            # 无序列表
            elif line.startswith("- "):
                nodes.append({
                    "type": "bulletedListItem",
                    "bulletedListItem": {"elements": [{"type": "textRun", "textRun": {"content": line[2:]}}], "level": 0}
                })
            # 普通文本
            else:
                nodes.append({
                    "type": "paragraph",
                    "paragraph": {"elements": [{"type": "textRun", "textRun": {"content": line}}]}
                })
        return nodes
    
    # 5. 写入飞书原生内容
    content_url = f"https://open.feishu.cn/open-apis/docx/v1/documents/{file_token}/content"
    content_data = {
        "requests": [{"insert": {"location": {"index": 0}, "nodes": md_to_feishu_nodes(summary_text)}}]
    }
    
    response = requests.patch(content_url, headers=headers, json=content_data, timeout=30, verify=False)
    response.raise_for_status()
    
    # 6. 返回飞书文档链接
    doc_url = f"https://www.feishu.cn/docs/d/{file_token}"
    return {
        "doc_id": file_token,
        "doc_url": doc_url,
        "title": title
    }
