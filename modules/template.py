# -*- coding: utf-8 -*-
"""
飞书风格模板渲染模块
"""
from typing import Dict, Any, List

def load_all_templates() -> Dict[str, Dict[str, str]]:
    """加载飞书风格模板"""
    all_templates = {
        "通用商务会议": {
            "base": """
# {会议核心信息[主题]}
## 一、会议核心信息
- 参与人：{会议核心信息[参与人]}
- 会议时间：{会议核心信息[会议时间]}
- 核心议题：{会议核心信息[核心议题]}

## 二、会议时间线
{章节时间线}

## 三、核心标签
【决策共识】{核心标签[决策共识]}
【核心逻辑】{核心标签[核心逻辑]}
【避雷提醒】{核心标签[避雷提醒]}
【机遇窗口】{核心标签[机遇窗口]}

## 四、双方资源与诉求
{双方资源/诉求}

## 五、合作模式与规划
### 短期规划（0-3个月）
{合作模式/规划[短期规划（0-3个月）]}
### 中长期规划（4-12个月）
{合作模式/规划[中长期规划（4-12个月）]}

## 六、核心结论与共识
{核心结论与共识}

## 七、待办事项
{待办事项与责任人}

## 八、问题与风险点
{问题与风险点}

## 九、下次会议安排
{下次会议安排}
            """,
        },
        "项目同步会议": {
            "base": """
# {会议核心信息[主题]}
## 一、会议核心信息
- 参与人：{会议核心信息[参与人]}
- 会议时间：{会议核心信息[会议时间]}
- 核心议题：{会议核心信息[核心议题]}

## 二、会议时间线
{章节时间线}

## 三、核心标签
【决策共识】{核心标签[决策共识]}
【核心逻辑】{核心标签[核心逻辑]}
【避雷提醒】{核心标签[避雷提醒]}
【机遇窗口】{核心标签[机遇窗口]}

## 四、项目当前进度
### 已完成项
{项目当前进度[已完成项]}
### 未完成项
{项目当前进度[未完成项]}
### 整体完成率
{项目当前进度[完成率]}

## 五、资源需求与协调
{资源需求与协调}

## 六、后续执行计划
### 短期（1周内）
{后续执行计划[短期（1周内）]}
### 中期（1个月内）
{后续执行计划[中期（1个月内）]}

## 七、核心结论与共识
{核心结论与共识}

## 八、待办事项
{待办事项与责任人}

## 九、问题与风险点
{问题与风险点}

## 十、下次会议安排
{下次会议安排}
            """,
        },
        "需求评审会议": {
            "base": """
# {会议核心信息[主题]}
## 一、会议核心信息
- 参与人：{会议核心信息[参与人]}
- 会议时间：{会议核心信息[会议时间]}
- 核心议题：{会议核心信息[核心议题]}

## 二、会议时间线
{章节时间线}

## 三、核心标签
【决策共识】{核心标签[决策共识]}
【核心逻辑】{核心标签[核心逻辑]}
【避雷提醒】{核心标签[避雷提醒]}
【机遇窗口】{核心标签[机遇窗口]}

## 四、需求核心内容
### 需求背景
{需求核心内容[需求背景]}
### 核心目标
{需求核心内容[核心目标]}
### 功能范围
{需求核心内容[功能范围]}

## 五、评审意见与结论
### 通过项
{评审意见与结论[通过项]}
### 修改项
{评审意见与结论[修改项]}
### 驳回项
{评审意见与结论[驳回项]}

## 六、需求修改要求
{需求修改要求}

## 七、核心结论与共识
{核心结论与共识}

## 八、待办事项
{待办事项与责任人}

## 九、问题与风险点
{问题与风险点}

## 十、下次会议安排
{下次会议安排}
            """,
        },
        "周度例会": {
            "base": """
# {会议核心信息[主题]}
## 一、会议核心信息
- 参与人：{会议核心信息[参与人]}
- 会议时间：{会议核心信息[会议时间]}
- 核心议题：{会议核心信息[核心议题]}

## 二、会议时间线
{章节时间线}

## 三、核心标签
【决策共识】{核心标签[决策共识]}
【核心逻辑】{核心标签[核心逻辑]}
【避雷提醒】{核心标签[避雷提醒]}
【机遇窗口】{核心标签[机遇窗口]}

## 四、本周工作完成情况
### 完成项
{本周工作完成情况[完成项]}
### 未完成项
{本周工作完成情况[未完成项]}

## 五、下周工作计划
{下周工作计划}

## 六、工作难点与协助需求
{工作难点与协助需求}

## 七、核心结论与共识
{核心结论与共识}

## 八、待办事项
{待办事项与责任人}

## 九、问题与风险点
{问题与风险点}

## 十、下次会议安排
{下次会议安排}
            """,
        }
    }
    return all_templates

def fill_template(extract_result: Dict[str, Any], template: Dict[str, str]) -> str:
    """渲染飞书风格模板"""
    # 处理时间线
    timeline_str = ""
    if "章节时间线" in extract_result and extract_result["章节时间线"]:
        for item in extract_result["章节时间线"]:
            if isinstance(item, dict):
                timeline_str += f"- **{item.get('时间区间', '未知')}**：{item.get('章节主题', '未知')} | {item.get('关键发言', '未知')}\n"
            else:
                timeline_str += f"- {item}\n"
    
    # 处理待办事项
    todo_str = ""
    if "待办事项与责任人" in extract_result:
        todos = extract_result["待办事项与责任人"]
        if isinstance(todos, list):
            for todo in todos:
                if isinstance(todo, dict):
                    todo_str += f"- **{todo.get('事项', '未知')}** | 责任人：{todo.get('责任人', '未知')} | 截止时间：{todo.get('截止时间', '未知')} | 优先级：{todo.get('优先级', '中')}\n"
                else:
                    todo_str += f"- {todo}\n"
        else:
            todo_str = todos
    
    # 处理列表类字段
    def format_list_field(field_value):
        if isinstance(field_value, list):
            return "\n".join([f"- {item}" for item in field_value])
        return str(field_value)
    
    # 递归替换变量
    def replace_vars(text: str) -> str:
        # 基础替换
        for key, value in extract_result.items():
            if isinstance(value, dict):
                for sub_key, sub_value in value.items():
                    # 处理嵌套字典（如合作模式/规划）
                    if isinstance(sub_value, dict):
                        for k, v in sub_value.items():
                            text = text.replace(f"{{{key}[{sub_key}][{k}]}}", format_list_field(v))
                    else:
                        text = text.replace(f"{{{key}[{sub_key}]}}", format_list_field(sub_value))
            else:
                text = text.replace(f"{{{key}}}", format_list_field(value))
        
        # 替换特殊字段
        text = text.replace("{章节时间线}", timeline_str)
        text = text.replace("{待办事项与责任人}", todo_str)
        return text
    
    # 填充模板
    filled_text = replace_vars(template["base"])
    # 清理空行和多余符号
    filled_text = "\n".join([line for line in filled_text.split("\n") if line.strip()])
    return filled_text

# 测试
if __name__ == '__main__':
    test_data = {
        "会议核心信息": {"主题": "测试会议", "参与人": "测试用户", "会议时间": "2026-02-26", "核心议题": "测试"},
        "章节时间线": [{"时间区间": "00:00:00-00:10:00", "章节主题": "测试", "关键发言": "测试"}],
        "核心标签": {"决策共识": "测试", "核心逻辑": "测试", "避雷提醒": "测试", "机遇窗口": "测试"},
        "待办事项与责任人": [{"事项": "测试", "责任人": "测试", "截止时间": "2026-02-28", "优先级": "高"}]
    }
    templates = load_all_templates()
    print(fill_template(test_data, templates["通用商务会议"]))
