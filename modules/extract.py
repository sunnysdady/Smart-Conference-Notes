# -*- coding: utf-8 -*-
"""
通用NLP信息提取模块（接入大模型）
核心功能：调用通义千问API，按飞书格式提取任意会议的结构化信息
支持：通用商务/项目同步/需求评审/周例会，返回标准化JSON
"""
from typing import List, Dict, Any
import json
import os
import requests  # 用requests直接调用API，避免langchain依赖问题

def get_llm_response(prompt: str, api_key: str) -> str:
    """
    调用通义千问API（轻量版，无需安装SDK，避免依赖问题）
    :param prompt: 提示词
    :param api_key: 通义千问API Key（从阿里云获取）
    :return: 大模型返回的文本
    """
    # 通义千问API地址（免费额度足够测试）
    url = "https://dashscope.aliyuncs.com/api/v1/services/aigc/text-generation/generation"
    
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    
    data = {
        "model": "qwen-turbo",  # 轻量版，响应快，免费额度多
        "input": {
            "messages": [
                {"role": "user", "content": prompt}
            ]
        },
        "parameters": {
            "temperature": 0.1,  # 低随机性，保证输出稳定
            "result_format": "text",
            "max_tokens": 2000  # 足够容纳会议纪要内容
        }
    }
    
    try:
        response = requests.post(url, headers=headers, json=data, timeout=30)
        response.raise_for_status()  # 抛出HTTP错误
        result = response.json()
        return result["output"]["choices"][0]["message"]["content"]
    except Exception as e:
        return json.dumps({"error": f"大模型调用失败：{str(e)}"}, ensure_ascii=False)

def extract_meeting_info(speech_list: List[Dict[str, Any]], template_type: str, api_key: str) -> Dict[str, Any]:
    """
    智能提取会议信息（真实调用大模型）
    :param speech_list: 预处理后的会议对话列表
    :param template_type: 会议模板类型
    :param api_key: 通义千问API Key
    :return: 飞书格式的结构化提取结果
    """
    # 1. 将对话列表转为纯文本（供大模型分析）
    meeting_text = ""
    for item in speech_list:
        meeting_text += f"{item['time']} {item['speaker']}：{item['content']}\n"
    
    # 2. 按模板类型生成标准化提示词（核心：让大模型严格按飞书格式返回）
    prompt_templates = {
        "通用商务会议": f"""
        请严格按照以下JSON格式分析会议文本，输出飞书风格的结构化会议纪要，仅返回JSON，无任何多余解释：
        {{
            "会议核心信息": {{
                "主题": "会议核心主题",
                "参与人": "参会人员",
                "会议时间": "会议时间",
                "核心议题": "核心讨论议题"
            }},
            "双方资源/诉求": "合作双方的核心资源、需求、合作意向（无则填'无'）",
            "合作模式/规划": "短期/中长期合作规划（无则填'无'）",
            "核心结论与共识": "会议达成的核心决策",
            "待办事项与责任人": "行动项+责任人+截止时间",
            "问题与风险点": "待解决问题/风险（无则填'无'）",
            "下次会议安排": "下次会议时间/议题（无则填'无'）"
        }}
        会议文本：{meeting_text}
        """,
        "项目同步会议": f"""
        请严格按照以下JSON格式分析会议文本，输出飞书风格的结构化会议纪要，仅返回JSON，无任何多余解释：
        {{
            "会议核心信息": {{
                "主题": "会议核心主题",
                "参与人": "参会人员",
                "会议时间": "会议时间",
                "核心议题": "核心讨论议题"
            }},
            "项目当前进度": "各模块进度/完成率/未完成项",
            "资源需求与协调": "技术/人力/物料需求（无则填'无'）",
            "后续执行计划": "阶段性目标/时间节点",
            "核心结论与共识": "会议达成的核心决策",
            "待办事项与责任人": "行动项+责任人+截止时间",
            "问题与风险点": "项目风险/执行难点（无则填'无'）",
            "下次会议安排": "下次会议时间/议题（无则填'无'）"
        }}
        会议文本：{meeting_text}
        """,
        "需求评审会议": f"""
        请严格按照以下JSON格式分析会议文本，输出飞书风格的结构化会议纪要，仅返回JSON，无任何多余解释：
        {{
            "会议核心信息": {{
                "主题": "会议核心主题",
                "参与人": "参会人员",
                "会议时间": "会议时间",
                "核心议题": "核心讨论议题"
            }},
            "需求核心内容": "需求背景/目标/核心功能",
            "评审意见与结论": "各部门意见/需求通过/修改/驳回",
            "需求修改要求": "修改点/标准/提交流程（无则填'无'）",
            "核心结论与共识": "会议达成的核心决策",
            "待办事项与责任人": "行动项+责任人+截止时间",
            "问题与风险点": "待解决问题/风险（无则填'无'）",
            "下次会议安排": "下次会议时间/议题（无则填'无'）"
        }}
        会议文本：{meeting_text}
        """,
        "周度例会": f"""
        请严格按照以下JSON格式分析会议文本，输出飞书风格的结构化会议纪要，仅返回JSON，无任何多余解释：
        {{
            "会议核心信息": {{
                "主题": "会议核心主题",
                "参与人": "参会人员",
                "会议时间": "会议时间",
                "核心议题": "核心讨论议题"
            }},
            "本周工作完成情况": "各岗位成果/完成率/未完成项",
            "下周工作计划": "各岗位目标/核心任务/优先级",
            "工作难点与协助需求": "遇到的问题/跨岗位协助需求（无则填'无'）",
            "核心结论与共识": "会议达成的核心决策",
            "待办事项与责任人": "行动项+责任人+截止时间",
            "问题与风险点": "待解决问题/风险（无则填'无'）",
            "下次会议安排": "下次会议时间/议题（无则填'无'）"
        }}
        会议文本：{meeting_text}
        """
    }
    
    # 3. 调用大模型
    if not api_key:
        return {"error": "请先在侧边栏输入大模型API Key"}
    
    prompt = prompt_templates[template_type]
    llm_result = get_llm_response(prompt, api_key)
    
    # 4. 解析大模型返回的JSON
    try:
        extract_result = json.loads(llm_result)
        return extract_result
    except:
        # 若大模型返回非JSON，返回模拟数据+提示
        return {
            "error": "大模型返回格式异常，使用模拟数据",
            "会议核心信息": {
                "主题": f"{template_type} - 核心事项讨论",
                "参与人": "未知",
                "会议时间": "未知",
                "核心议题": "未知"
            },
            "核心结论与共识": "请检查API Key或会议文本是否完整",
            "待办事项与责任人": "无",
            "问题与风险点": "无",
            "下次会议安排": "无"
        }

# 本地测试（需替换自己的API Key）
if __name__ == '__main__':
    test_speech = [
        {"time": "00:00:00", "speaker": "主持人", "content": "本次会议讨论XX项目进度，开发完成80%，下周联调"},
        {"time": "00:05:00", "speaker": "技术负责人", "content": "需要产品侧今日提供测试用例，否则联调延期"}
    ]
    test_api_key = "你的通义千问API Key"  # 替换为真实Key
    print(extract_meeting_info(test_speech, "项目同步会议", test_api_key))
