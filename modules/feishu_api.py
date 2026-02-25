# -*- coding: utf-8 -*-
"""
飞书API模块（最终最终版：适配新版飞书文档，解决所有404）
"""
import requests
import json
from typing import Dict, Any

# ========== 你的飞书配置 ==========
FEISHU_CONFIG = {
    "APP_ID": "cli_a916f070b0f8dcd6",
    "APP_SECRET": "gHOYZxXsoTXpmsnyf37C5dqcN4tOkibW",
    "TENANT_ACCESS_TOKEN": "",
    "FOLDER_TOKEN": "",  # 可选：飞书文件夹token
    "TABLE_TOKEN": ""    # 可选：多维表格token
}
# =================================

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
    适配新版飞书文档：直接创建+写入Markdown内容（解决404）
    """
    # 1. 生成飞书风格纪要内容（Markdown）
    from modules.extract import extract_meeting_info
    from modules.preprocess import parse_speech
    from modules.template import fill_template, load_all_templates
    
    speech_list = parse_speech(meeting_text)
    extract_result = extract_meeting_info(speech_list, template_type)
    templates = load_all_templates()
    summary_text = fill_template(extract_result, templates[template_type])
    
    # 2. 获取Token
    if not FEISHU_CONFIG["TENANT_ACCESS_TOKEN"]:
        get_tenant_access_token()
    token = FEISHU_CONFIG["TENANT_ACCESS_TOKEN"]
    
    # 3. 创建新版飞书文档（用drive/v1接口，不会404）
    create_url = "https://open.feishu.cn/open-apis/drive/v1/files/create"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    create_data = {
        "title": title,
        "type": "docx",
        "folder_token": FEISHU_CONFIG["FOLDER_TOKEN"]  # 可选：指定文件夹
    }
    
    response = requests.post(create_url, headers=headers, json=create_data, timeout=30, verify=False)
    response.raise_for_status()
    create_result = response.json()
    
    if create_result.get("code") != 0:
        raise Exception(f"创建文档失败：{create_result.get('msg')}")
    
    # 获取新版文档的file_token（核心，替代document_id）
    file_token = create_result["data"]["file_token"]
    
    # 4. 写入Markdown内容到新版文档（解决404的核心步骤）
    # 4.1 获取上传凭证
    upload_url = f"https://open.feishu.cn/open-apis/drive/v1/files/{file_token}/media/upload_all"
    upload_headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "multipart/form-data"
    }
    
    # 4.2 构造上传数据（直接上传Markdown内容）
    files = {
        "file": (f"{title}.md", summary_text.encode("utf-8"), "text/markdown")
    }
    data = {
        "file_type": "docx",
        "override": True
    }
    
    # 4.3 执行上传（写入内容）
    response = requests.post(upload_url, headers=upload_headers, files=files, data=data, timeout=30, verify=False)
    response.raise_for_status()
    upload_result = response.json()
    
    if upload_result.get("code") != 0:
        raise Exception(f"写入文档内容失败：{upload_result.get('msg')}")
    
    # 5. 拼接飞书文档链接（新版文档通用格式）
    doc_url = f"https://www.feishu.cn/docs/d/{file_token}"
    
    # 6. 同步待办事项到多维表格（可选）
    if FEISHU_CONFIG["TABLE_TOKEN"] and "待办事项与责任人" in extract_result:
        sync_todo_to_bitable(extract_result["待办事项与责任人"], title)
    
    return {
        "doc_id": file_token,
        "doc_url": doc_url,
        "title": title
    }

def sync_todo_to_bitable(todo_list: list, meeting_title: str) -> bool:
    """同步待办事项到飞书多维表格"""
    if not FEISHU_CONFIG["TABLE_TOKEN"] or not todo_list:
        return False
    
    token = FEISHU_CONFIG["TENANT_ACCESS_TOKEN"]
    # 替换为你的多维表格table_id（从URL获取：tbl开头的字符串）
    table_id = "tblXXXXXXXX"  # 需手动替换为你的实际table_id
    url = f"https://open.feishu.cn/open-apis/bitable/v1/apps/{FEISHU_CONFIG['TABLE_TOKEN']}/tables/{table_id}/records"
    
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
            except Exception as e:
                print(f"同步待办失败：{e}")
                continue
    
    return True

def get_folder_token_by_url(folder_url: str) -> str:
    """从飞书文件夹URL提取folder_token"""
    # 示例URL：https://www.feishu.cn/drive/folder/fldXXXXXXXX
    if "folder/" in folder_url:
        return folder_url.split("folder/")[-1]
    return ""
