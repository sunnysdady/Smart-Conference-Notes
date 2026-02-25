# -*- coding: utf-8 -*-
"""
通用NLP信息提取模块（嵌入API Key）
"""
from typing import List, Dict, Any
import json
import os
import requests

# 👇 直接嵌入你的API Key
FIXED_API_KEY = "sk-ecb46034c430477e9c9a4b4fd6589742"

def get_llm_response(prompt: str, api_key: str = FIXED_API_KEY) -> str:
    """调用通义千问API（默认使用嵌入的Key）"""
    url = "https://dashscope.aliyuncs.com/api/v1/services/aigc/text-generation/generation"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    data = {
        "model": "qwen-turbo",
        "input": {"messages": [{"role": "user", "content": prompt}]},
        "parameters": {"temperature": 0.1, "result_format": "text", "max_tokens": 2000}
    }
    try:
        response = requests.post(url, headers=headers, json=data, timeout=30)
        response.raise_for_status()
        result = response.json()
        return result["output"]["text"]  # 新版API字段
    except Exception as e:
        return json.dumps({"error": f"大模型调用失败：{str(e)}"}, ensure_ascii=False)

def extract_meeting_info(speech_list: List[Dict[str, Any]], template_type: str, api_key: str = FIXED_API_KEY) -> Dict[str, Any]:
    """智能提取会议信息（默认使用嵌入的Key）"""
    # 1. 拼接会议文本
    meeting_text = "\n".join([f"{item['time']} {item['speaker']}：{item['content']}" for item in speech_list])
    
    # 2. 模板提示词
    prompt_templates = {
        "通用商务会议": f"""
        请严格按照以下JSON格式分析会议文本，仅返回JSON，无任何多余解释：
        {{
            "会议核心信息": {{
                "主题": "会议核心主题",
                "参与人": "参会人员",
                "会议时间": "会议时间",
                "核心议题": "核心讨论议题"
            }},
            "双方资源/诉求": "合作双方的核心资源/需求（无则填'无'）",
            "合作模式/规划": "短期/中长期合作规划（无则填'无'）",
            "核心结论与共识": "会议达成的核心决策",
            "待办事项与责任人": "行动项+责任人+截止时间",
            "问题与风险点": "待解决问题/风险（无则填'无'）",
            "下次会议安排": "下次会议时间/议题（无则填'无'）"
        }}
        会议文本：{meeting_text}
        """,
        "项目同步会议": f"""
        请严格按照以下JSON格式分析会议文本，仅返回JSON，无任何多余解释：
        {{
            "会议核心信息": {{
                "主题": "会议核心主题",
                "参与人": "参会人员",
                "会议时间": "会议时间",
                "核心议题": "核心讨论议题"
            }},
            "项目当前进度": "各模块进度/完成率/未完成项",
            "资源需求与协调": "技术/人力需求（无则填'无'）",
            "后续执行计划": "阶段性目标/时间节点",
            "核心结论与共识": "会议达成的核心决策",
            "待办事项与责任人": "行动项+责任人+截止时间",
            "问题与风险点": "项目风险/执行难点（无则填'无'）",
            "下次会议安排": "下次会议时间/议题（无则填'无'）"
        }}
        会议文本：{meeting_text}
        """,
        "需求评审会议": f"""
        请严格按照以下JSON格式分析会议文本，仅返回JSON，无任何多余解释：
        {{
            "会议核心信息": {{
                "主题": "会议核心主题",
                "参与人": "参会人员",
                "会议时间": "会议时间",
                "核心议题": "核心讨论议题"
            }},
            "需求核心内容": "需求背景/目标/核心功能",
            "评审意见与结论": "各部门意见/需求通过/修改/驳回",
            "需求修改要求": "修改点/标准（无则填'无'）",
            "核心结论与共识": "会议达成的核心决策",
            "待办事项与责任人": "行动项+责任人+截止时间",
            "问题与风险点": "待解决问题/风险（无则填'无'）",
            "下次会议安排": "下次会议时间/议题（无则填'无'）"
        }}
        会议文本：{meeting_text}
        """,
        "周度例会": f"""
        请严格按照以下JSON格式分析会议文本，仅返回JSON，无任何多余解释：
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
    
    # 3. 调用大模型（无需传Key，使用默认值）
    prompt = prompt_templates[template_type]
    llm_result = get_llm_response(prompt)
    
    # 4. 解析结果
    try:
        return json.loads(llm_result)
    except:
        return {
            "error": "大模型返回格式异常，使用模拟数据",
            "会议核心信息": {
                "主题": f"{template_type} - 核心事项讨论",
                "参与人": "未知",
                "会议时间": "未知",
                "核心议题": "未知"
            },
            "核心结论与共识": "请检查会议文本是否完整",
            "待办事项与责任人": "无",
            "问题与风险点": "无",
            "下次会议安排": "无"
        }

# 本地测试
if __name__ == '__main__':
    test_speech = [{"time": "00:00:00", "speaker": "主持人", "content": "测试会议内容"}]
    print(extract_meeting_info(test_speech, "项目同步会议"))
