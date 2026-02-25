# -*- coding: utf-8 -*-
"""
飞书API模块（最终修复版：解决KeyError+404）
"""
import requests
import json
from typing import Dict, Any

# ========== 你的飞书配置（直接填好） ==========
FEISHU_CONFIG = {
    "APP_ID": "cli_a916f070b0f8dcd6",
    "APP_SECRET": "gHOYZxXsoTXpmsnyf37C5dqcN4tOkibW",
    "TENANT_ACCESS_TOKEN": "",
    "FOLDER_TOKEN": "",  # 可选：飞书文件夹token（从文件夹URL获取）
    "TABLE_TOKEN": ""    # 可选：飞书多维表格token（同步待办事项用）
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
    最终版：一键创建飞书原生智能纪要文档（解决404+KeyError）
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
    
    # 3. 创建飞书文档（修复404+KeyError）
    create_url = "https://open.feishu.cn/open-apis/docx/v1/documents"
    headers = {
        "Authorization": f"Bearer {FEISHU_CONFIG['TENANT_ACCESS_TOKEN']}",
        "Content-Type": "application/json"
    }
    create_data = {
        "title": title,
        "folder_token": FEISHU_CONFIG["FOLDER_TOKEN"],
        "doc_type": "docx"
    }
    
    response = requests.post(create_url, headers=headers, json=create_data, timeout=30, verify=False)
    response.raise_for_status()
    create_result = response.json()
    
    # 调试输出：打印完整返回（方便排查）
    print("飞书API返回数据：", json.dumps(create_result, ensure_ascii=False, indent=2))
    
    if create_result.get("code") != 0:
        raise Exception(f"创建文档失败：{create_result.get('msg')}")
    
    # 🌟 核心修复：兼容所有可能的文档ID字段名
    data = create_result.get("data", {})
    document_id = None
    # 按优先级查找字段
    if "document_id" in data:
        document_id = data["document_id"]
    elif "file_token" in data:
        document_id = data["file_token"]
    elif "id" in data:
        document_id = data["id"]
    else:
        raise Exception(f"无法找到文档ID！API返回的data：{data}")
    
    # 4. Markdown 转飞书原生节点
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
            # 飞书高亮标签块
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
            # 飞书待办事项
            elif line.startswith("✅ "):
                nodes.append({
                    "type": "toDo",
                    "toDo": {
                        "checked": False,
                        "elements": [{"type": "textRun", "textRun": {"content": line[2:]}}]
                    }
                })
            # 普通文本
            else:
                nodes.append({
                    "type": "paragraph",
                    "paragraph": {"elements": [{"type": "textRun", "textRun": {"content": line}}]}
                })
        return nodes
    
    # 5. 写入飞书原生内容
    content_url = f"https://open.feishu.cn/open-apis/docx/v1/documents/{document_id}/content"
    content_data = {
        "requests": [{"insert": {"location": {"index": 0}, "nodes": md_to_feishu_nodes(summary_text)}}]
    }
    
    response = requests.patch(content_url, headers=headers, json=content_data, timeout=30, verify=False)
    response.raise_for_status()
    
    # 6. 拼接飞书文档链接
    doc_url = f"https://www.feishu.cn/docs/d/{document_id}"
    
    # 7. 同步待办事项到多维表格（可选）
    if FEISHU_CONFIG["TABLE_TOKEN"] and "待办事项与责任人" in extract_result:
        sync_todo_to_bitable(extract_result["待办事项与责任人"], title)
    
    return {
        "doc_id": document_id,
        "doc_url": doc_url,
        "title": title
    }

def sync_todo_to_bitable(todo_list: list, meeting_title: str) -> bool:
    """同步待办事项到飞书多维表格"""
    if not FEISHU_CONFIG["TABLE_TOKEN"] or not todo_list:
        return False
    
    token = FEISHU_CONFIG["TENANT_ACCESS_TOKEN"]
    # 替换为你的多维表格table_id（从URL获取）
    url = f"https://open.feishu.cn/open-apis/bitable/v1/apps/{FEISHU_CONFIG['TABLE_TOKEN']}/tables/tblXXXXXXXX/records"
    
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    
    for todo in todo_list:
        if isinstance(todo, dict):
            data = {
                "fields": {
                    "会议标题": meeting_title,
                    "待办事项": todo.get("事项", ""),
                    "责任人": todo.get("责任人", ""),
                    "截止时间": todo.get("截止时间", ""),
                    "优先级": todo.get("优先级", "中")
                }
            }
            try:
                requests.post(url, headers=headers, json=data, timeout=30, verify=False)
            except:
                continue
    
    return True

def get_folder_token_by_url(folder_url: str) -> str:
    """从飞书文件夹URL提取folder_token"""
    if "folder/" in folder_url:
        return folder_url.split("folder/")[-1]
    return ""
