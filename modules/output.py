# -*- coding: utf-8 -*-
"""
通用格式输出模块
核心功能：将标准化纪要文本，保存为MD/Word通用格式
适配所有会议类型，文件命名标准化，无行业/场景限制
仅Python语法编写，无实际文件写入，模拟文件保存
"""
# 👇 移除 from typing import str 这行
# from typing import str 

def save_md(summary_text: str, save_path: str = "通用会议纪要.md") -> str:  # str直接使用，无需导入
    """
    通用MD格式保存：适配所有会议纪要，纯文本排版，支持所有编辑器
    :param summary_text: 标准化填充后的纪要文本
    :param save_path: 保存路径（标准化命名：会议类型_会议纪要.md）
    :return: 模拟保存路径，无实际文件操作
    """
    # 仅模拟文件保存，返回标准化路径
    return save_path

def save_word(summary_text: str, save_path: str = "通用会议纪要.docx") -> str:  # str直接使用，无需导入
    """
    通用Word格式保存：适配办公场景，标准化排版，支持Word/ WPS打开
    :param summary_text: 标准化填充后的纪要文本
    :param save_path: 保存路径（标准化命名：会议类型_会议纪要.docx）
    :return: 模拟保存路径，无实际文件操作
    """
    # 仅模拟文件保存，返回标准化路径
    return save_path

# 通用测试（仅Python语法，无实际执行）
if __name__ == '__main__':
    test_summary = "# 测试项目同步会议纪要\n## 一、会议基本信息\n- 时间：2026-XX-XX"
    # 测试标准化命名
    print(save_md(test_summary, "项目同步会议_会议纪要.md"))
    print(save_word(test_summary, "项目同步会议_会议纪要.docx"))
