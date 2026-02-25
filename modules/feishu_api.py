# -*- coding: utf-8 -*-
"""
飞书API调用模块
已嵌入配置：App ID/Secret/Webhook | 修复机器人msg_type报错 | 适配飞书最新接口
"""
import requests
import json
from typing import Dict, Any, Optional

# ========== 已嵌入你的飞书配置，无需修改 ==========
FEISHU_CONFIG = {
    "APP_ID": "cli_a916f070b0f8dcd6",
    "APP_SECRET": "gHOYZxXsoTXpmsnyf37C5dqcN4tOkibW",
    "ROBOT_WEBHOOK": "https://open.feishu.cn/open-apis/bot/v2/hook/d03aa92c-4ba8-4cc9-9df1-e2048d2344d0",
    "TENANT_ACCESS_TOKEN": ""
}
# ==================================================

def get_tenant_access_token() -> str:
    """获取飞书租户级token（有效期2小时，自动缓存）"""
    url = "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal"
    headers = {"Content-Type": "application/json"}
    data = {
        "app_id": FEISHU_CONFIG["APP_ID"],
        "app_secret": FEISHU_CONFIG["APP_SECRET"]
    }
    try:
        response = requests.post(url, headers=headers, json=data, timeout=30)
        response.raise_for_status()
        result = response.json()
        if result.get("code") == 0:
            FEISHU_CONFIG["TENANT_ACCESS_TOKEN"] = result["tenant_access_token"]
            return result["tenant_access_token"]
        else:
            raise Exception(f"获取token失败：{result.get('msg', '未知错误')}")
    except Exception as e:
        raise Exception(f"飞书API调用失败：{str(e)}")

def create_feishu_doc(title: str, content: str) -> Dict[str, Any]:
    """
    创建飞书文档并写入飞书原生风格内容
    :param title: 文档标题
    :param content: 飞书风格纪要（Markdown格式）
    :return: 文档ID+链接
    """
    # 确保token有效
    if not FEISHU_CONFIG["TENANT_ACCESS_TOKEN"]:
        get_tenant_access_token()
    # 1. 创建空白文档
    create_url = "https://open.feishu.cn/open-apis/docx/v1/documents"
    headers = {
        "Authorization": f"Bearer {FEISHU_CONFIG['TENANT_ACCESS_TOKEN']}",
        "Content-Type": "application/json"
    }
    create_data = {"title": title, "doc_type": "docx"}
    response = requests.post(create_url, headers=headers, json=create_data, timeout=30)
    response.raise_for_status()
    create_result = response.json()
    if create_result.get("code") != 0:
        raise Exception(f"创建文档失败：{create_result.get('msg', '未知错误')}")
    doc_id = create_result["data"]["document_id"]
    
    # 2. Markdown转飞书文档节点（适配飞书最新格式）
    def md_to_feishu_nodes(md_content: str) -> list:
        nodes = []
        lines = md_content.split("\n")
        for line in lines:
            line = line.strip()
            if not line:
                continue
            # 标题1/2
            if line.startswith("# "):
                nodes.append({"type": "heading1", "heading1": {"elements": [{"type": "textRun", "textRun": {"content": line[2:]}}]}})
            elif line.startswith("## "):
                nodes.append({"type": "heading2", "heading2": {"elements": [{"type": "textRun", "textRun": {"content": line[2:]}}]}})
            # 飞书高亮标签块（决策共识/核心逻辑等）
            elif line.startswith("【") and "】" in line:
                tag_name, tag_content = line.split("】", 1)
                tag_name = tag_name[1:]
                nodes.append({
                    "type": "paragraph",
                    "paragraph": {
                        "style": {"backgroundColor": "#f0f7ff", "borderLeft": {"color": "#1890ff", "width": 4}},
                        "elements": [
                            {"type": "textRun", "textRun": {"content": f"【{tag_name}】 ", "style": {"bold": True}}},
                            {"type": "textRun", "textRun": {"content": tag_content.strip()}}
                        ]
                    }
                })
            # 无序列表
            elif line.startswith("- "):
                nodes.append({"type": "bulletedListItem", "bulletedListItem": {"elements": [{"type": "textRun", "textRun": {"content": line[2:]}}], "level": 0}})
            # 普通文本
            else:
                nodes.append({"type": "paragraph", "paragraph": {"elements": [{"type": "textRun", "textRun": {"content": line}}]}})
        return nodes
    
    # 3. 写入文档内容
    content_url = f"https://open.feishu.cn/open-apis/docx/v1/documents/{doc_id}/content"
    content_data = {
        "requests": [{"insert": {"location": {"index": 0}, "nodes": md_to_feishu_nodes(content)}}]
    }
    requests.patch(content_url, headers=headers, json=content_data, timeout=30)
    # 拼接飞书文档可访问链接
    doc_url = f"https://www.feishu.cn/docs/d/{doc_id}"
    return {"doc_id": doc_id, "doc_url": doc_url, "title": title}

def send_feishu_robot_msg(title: str, doc_url: str) -> bool:
    """
    修复msg_type报错！飞书机器人发送**纯文本+链接**通知（适配最新接口，必传msg_type）
    :param title: 纪要标题
    :param doc_url: 飞书文档链接
    :return: 是否发送成功
    """
    if not FEISHU_CONFIG["ROBOT_WEBHOOK"]:
        return False
    url = FEISHU_CONFIG["ROBOT_WEBHOOK"]
    headers = {"Content-Type": "application/json; charset=utf-8"}
    # 🌟 修复核心：指定msg_type为text（飞书必传），格式极简不易错
    data = {
        "msg_type": "text",  # 必传字段，解决params error, msg_type need
        "content": {
            "text": f"✅ 飞书风格智能会议纪要生成完成！\n📋 纪要标题：{title}\n🔗 查看文档：{doc_url}"
        }
    }
    try:
        response = requests.post(url, headers=headers, json=data, timeout=30)
        result = response.json()
        if result.get("code") == 0:
            return True
        else:
            print(f"机器人消息发送失败：{result}")
            return False
    except Exception as e:
        print(f"机器人消息调用异常：{str(e)}")
        return False

# 本地测试（可选，直接运行该文件即可测试飞书接口）
if __name__ == '__main__':
    test_content = """# 测试会议纪要
## 一、会议核心信息
- 参与人：张三（产品）、李四（技术）
- 会议时间：2026-02-26
- 核心议题：XX项目联调规划

【决策共识】下周一开始项目联调，产品侧提前提供测试用例
【核心逻辑】测试用例到位是联调顺利的前提
## 二、待办事项
- **提供测试用例** | 责任人：张三 | 截止时间：2026-02-28 | 优先级：高
"""
    # 测试创建文档+发送机器人消息
    try:
        doc_info = create_feishu_doc("测试飞书纪要_修复版", test_content)
        print(f"文档创建成功：{doc_info['doc_url']}")
        send_ok = send_feishu_robot_msg(doc_info["title"], doc_info["doc_url"])
        print(f"机器人消息发送：{'成功' if send_ok else '失败'}")
    except Exception as e:
        print(f"测试失败：{str(e)}")
