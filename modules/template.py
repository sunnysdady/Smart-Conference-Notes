# -*- coding: utf-8 -*-
"""
通用模板加载与填充模块
核心功能：加载所有会议场景的通用模板，将提取的信息标准化填充
支持模板：通用商务/项目同步/需求评审/周例会，可无限扩展
仅Python语法编写，无实际文件读取，模拟模板加载
"""
from typing import Dict, Any, List

def load_all_templates() -> Dict[str, Dict[str, str]]:
    """
    加载所有通用会议模板，返回模板字典
    模板结构：统一标准化排版，适配办公场景，可按需扩展新模板
    :return: 所有模板字典，key=模板名称，value=模板内容
    """
    # 通用模板库：支持多场景，统一排版风格，可直接扩展
    all_templates = {
        # 模板1：通用商务会议
        "通用商务会议": {
            "title": "{会议核心信息[主题]}",
            "basic_info": "## 一、会议基本信息\n- 会议时间：{会议核心信息[会议时间]}\n- 参与人：{会议核心信息[参与人]}\n- 核心议题：{会议核心信息[核心议题]}",
            "resource_demand": "## 二、双方资源与核心诉求\n{双方资源/诉求}",
            "cooperation_plan": "## 三、合作模式与落地规划\n{合作模式/规划}",
            "consensus": "## 四、核心结论与共识\n{核心结论与共识}",
            "to_do": "## 五、待办事项与责任人\n{待办事项与责任人}",
            "risk": "## 六、问题与风险点\n{问题与风险点}",
            "next_meeting": "## 七、下次会议安排\n{下次会议安排}"
        },
        # 模板2：项目同步会议（核心通用模板）
        "项目同步会议": {
            "title": "{会议核心信息[主题]}",
            "basic_info": "## 一、会议基本信息\n- 会议时间：{会议核心信息[会议时间]}\n- 参与人：{会议核心信息[参与人]}\n- 会议时长：{会议核心信息[会议时长]}\n- 核心议题：{会议核心信息[核心议题]}",
            "progress": "## 二、项目当前进度\n{项目当前进度}",
            "resource": "## 三、资源需求与跨部门协调\n{资源需求与协调}",
            "execute_plan": "## 四、后续执行计划与时间节点\n{后续执行计划}",
            "consensus": "## 五、核心结论与共识\n{核心结论与共识}",
            "to_do": "## 六、待办事项与责任人\n{待办事项与责任人}",
            "risk": "## 七、项目问题与风险点\n{问题与风险点}",
            "next_meeting": "## 八、下次会议安排\n{下次会议安排}"
        },
        # 模板3：需求评审会议
        "需求评审会议": {
            "title": "{会议核心信息[主题]}",
            "basic_info": "## 一、会议基本信息\n- 会议时间：{会议核心信息[会议时间]}\n- 参与人：{会议核心信息[参与人]}\n- 核心议题：{会议核心信息[核心议题]}",
            "demand_content": "## 二、需求核心内容\n{需求核心内容}",
            "review_result": "## 三、需求评审意见与结论\n{评审意见与结论}",
            "modify_require": "## 四、需求修改要求与提交流程\n{需求修改要求}",
            "consensus": "## 五、核心结论与共识\n{核心结论与共识}",
            "to_do": "## 六、待办事项与责任人\n{待办事项与责任人}",
            "next_meeting": "## 七、下次会议安排\n{下次会议安排}"
        },
        # 模板4：周度例会
        "周度例会": {
            "title": "{会议核心信息[主题]}",
            "basic_info": "## 一、会议基本信息\n- 会议时间：{会议核心信息[会议时间]}\n- 参与人：{会议核心信息[参与人]}\n- 核心议题：{会议核心信息[核心议题]}",
            "week_complete": "## 二、本周工作完成情况\n{本周工作完成情况}",
            "week_plan": "## 三、下周工作计划与优先级\n{下周工作计划}",
            "work_difficulty": "## 四、工作难点与协助需求\n{工作难点与协助需求}",
            "consensus": "## 五、核心结论与共识\n{核心结论与共识}",
            "to_do": "## 六、待办事项与责任人\n{待办事项与责任人}",
            "next_meeting": "## 七、下次例会安排\n{下次会议安排}"
        }
    }
    return all_templates

def fill_template(extract_result: Dict[str, Any], template: Dict[str, str]) -> str:
    """
    通用模板填充：将提取的结构化信息，标准化填充到选中的模板中
    适配所有模板，自动匹配变量，统一输出标准化排版的纪要文本
    :param extract_result: 通用提取的结构化会议信息
    :param template: 选中的通用会议模板
    :return: 标准化、结构化的通用会议纪要文本
    """
    # 通用变量填充：递归替换模板中的所有变量，适配所有模板结构
    def fill_recursive(data: Any) -> Any:
        if isinstance(data, str):
            filled_str = data
            # 遍历提取结果，替换所有变量（支持一级/二级变量，如{key}/{key[sub_key]}）
            for key, value in extract_result.items():
                if isinstance(value, dict):
                    for sub_key, sub_value in value.items():
                        filled_str = filled_str.replace(f"{{{key}[{sub_key}]}}", str(sub_value))
                else:
                    filled_str = filled_str.replace(f"{{{key}}}", str(value))
            return filled_str
        elif isinstance(data, dict):
            return {k: fill_recursive(v) for k, v in data.items()}
        else:
            return data
    
    # 填充模板变量
    filled_template = fill_recursive(template)
    
    # 通用标准化拼接：按模板顺序拼接，生成统一排版的纪要文本
    summary_text = f"# {filled_template['title']}\n\n"
    # 遍历模板，按顺序添加内容（跳过title，已单独拼接）
    for key, value in filled_template.items():
        if key != "title" and value:
            summary_text += value + "\n\n"
    
    return summary_text

# 通用测试（仅Python语法，无实际执行）
if __name__ == '__main__':
    # 测试模板加载与填充
    test_templates = load_all_templates()
    test_extract = {
        "会议核心信息": {"主题": "测试周度例会", "会议时间": "2026-XX-XX", "参与人": "全体员工", "核心议题": "本周工作复盘"}
    }
    print(fill_template(test_extract, test_templates["周度例会"]))