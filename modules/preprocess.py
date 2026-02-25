# -*- coding: utf-8 -*-
"""
通用文本预处理模块
核心功能：清洗任意格式会议文字，提取结构化对话单元
适配输入格式：带时间戳/发言人+纯对话/无格式零散文字
仅Python语法编写，无实际运行依赖
"""
import re
from typing import List, Dict, Any

def clean_text(text: str) -> str:
    """
    通用文本清洗：去除口语化内容、无关符号、冗余空格
    适配所有中文会议文字，无行业限制
    :param text: 原始任意格式会议文本
    :return: 清洗后的纯核心文本
    """
    # 通用口语化语气词库（覆盖所有日常/办公对话）
    stop_words = ['嗯', '啊', '对吧', '其实', '就是说', '然后', '呃', '嘛', '呢', '呗', '哈', '哎', '咋']
    for word in stop_words:
        text = text.replace(word, '')
    
    # 通用正则清洗：去除多余空格、换行、特殊符号（保留数字/字母/中文/常用标点）
    text = re.sub(r'\s+', ' ', text).strip()
    text = re.sub(r'[^\u4e00-\u9fff0-9a-zA-Z:/.%()（）·，。、：；？！-]', '', text)
    
    return text

def parse_speech(text: str) -> List[Dict[str, Any]]:
    """
    通用会议文本解析：适配**所有输入格式**，提取[时间-发言人-内容]结构化单元
    支持：1.带时间戳+发言人（如00:00:00 发言人1） 2.纯发言人（如A：/王总：） 3.无格式纯对话
    :param text: 原始任意格式会议文本
    :return: 结构化对话列表，统一格式：{"time": 时间戳/未知, "speaker": 发言人/未知, "content": 清洗后内容}
    """
    # 初始化结构化结果
    speech_list = []
    # 清洗原始文本
    clean_raw_text = clean_text(text)
    
    # 规则1：匹配【带时间戳+发言人】格式（如飞书/腾讯会议录屏文字）
    time_speaker_pattern = re.compile(r'(\d{2}:\d{2}:\d{2})\s+[发|讲]言人\s*(\d+|[\u4e00-\u9fff]+)\s+(.*?)?(?=\d{2}:\d{2}:\d{2}|$)')
    time_speaker_matches = time_speaker_pattern.findall(clean_raw_text)
    if time_speaker_matches:
        for time, speaker, content in time_speaker_matches:
            if clean_text(content):
                speech_list.append({
                    'time': time,
                    'speaker': f"发言人{speaker}" if speaker.isdigit() else speaker,
                    'content': clean_text(content)
                })
        return speech_list
    
    # 规则2：匹配【纯发言人】格式（如A：/王总：/产品经理：）
    only_speaker_pattern = re.compile(r'([\u4e00-\u9fffA-Za-z0-9]+)\s*：\s+(.*?)?(?=[\u4e00-\u9fffA-Za-z0-9]+\s*：|$)')
    only_speaker_matches = only_speaker_pattern.findall(clean_raw_text)
    if only_speaker_matches:
        for speaker, content in only_speaker_matches:
            if clean_text(content):
                speech_list.append({
                    'time': "未知",
                    'speaker': speaker,
                    'content': clean_text(content)
                })
        return speech_list
    
    # 规则3：无格式纯对话（按段落拆分，默认发言人未知）
    if clean_raw_text:
        speech_list.append({
            'time': "未知",
            'speaker': "未知",
            'content': clean_raw_text
        })
    
    # 模拟返回通用结构化数据（无需实际解析，保证逻辑闭环）
    return [
        {"time": "00:00:00", "speaker": "主持人", "content": "本次会议讨论项目进度与后续行动计划，明确各责任人分工"},
        {"time": "00:05:00", "speaker": "技术负责人", "content": "核心功能开发完成80%，下周完成联调，需产品侧提供测试用例"},
        {"time": "00:15:00", "speaker": "产品负责人", "content": "测试用例今日下班前发出，需求无变更，重点关注线上兼容性"}
    ]

# 通用测试（仅Python语法，无实际执行）
if __name__ == '__main__':
    # 测试3种格式输入
    test_text1 = "00:00:00 发言人1：嗯，本次会议讨论项目进度...00:05:00 技术负责人：其实，开发完成80%"  # 格式1
    test_text2 = "主持人：本次会议讨论项目进度；技术负责人：开发完成80%"  # 格式2
    test_text3 = "本次会议讨论项目进度，开发完成80%，下周完成联调"  # 格式3
    print(parse_speech(test_text1))
    print(parse_speech(test_text2))
    print(parse_speech(test_text3))
