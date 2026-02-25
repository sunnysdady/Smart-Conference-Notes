# modules/extract.py
from langchain.prompts import PromptTemplate
from langchain_community.llms import Tongyi  # 以通义千问为例
import os
import json

def extract_meeting_info(speech_list: List[Dict[str, Any]], template_type: str) -> Dict[str, Any]:
    """
    调用大模型，根据会议文本和模板类型，动态提取结构化信息
    """
    # 1. 将对话列表转为纯文本
    meeting_text = '\n'.join([f"{item['time']}-{item['speaker']}: {item['content']}" for item in speech_list])
    
    # 2. 根据模板类型，动态生成提示词
    if template_type == "通用商务会议":
        prompt_template = PromptTemplate(
            input_variables=["meeting_text"],
            template="""
            分析以下商务会议记录，按要求输出JSON格式，无多余解释：
            1. 会议核心信息：主题、参与人、会议时间、核心议题
            2. 双方资源/诉求：合作双方的核心资源、需求、合作意向
            3. 合作模式/规划：短期合作动作、中长期合作规划、落地路径
            4. 核心结论与共识：会议达成的统一决策、核心共识
            5. 待办事项与责任人：所有行动项、执行要求、责任人、截止时间
            6. 问题与风险点：会议提出的待解决问题、项目风险、执行难点
            7. 下次会议安排：下次会议时间、议题、参与人

            会议记录：{meeting_text}
            """
        )
    # ... 其他模板的提示词 ...

    # 3. 调用大模型
    llm = Tongyi(model_name="qwen-plus", temperature=0.1)
    prompt = prompt_template.format(meeting_text=meeting_text)
    result = llm.invoke(prompt)
    
    # 4. 解析并返回JSON结果
    try:
        return json.loads(result)
    except:
        return {"error": "大模型分析失败，请检查会议文本"}
