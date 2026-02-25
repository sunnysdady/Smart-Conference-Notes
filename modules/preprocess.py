# -*- coding: utf-8 -*-
"""
通用文本预处理模块
"""
from typing import List, Dict, Any

def parse_speech(raw_text: str) -> List[Dict[str, Any]]:
    """
    解析原始会议文本为结构化对话列表
    支持格式：时间-发言人：内容 / 发言人：内容 / 纯文本
    """
    speech_list = []
    lines = raw_text.strip().split("\n")
    for idx, line in enumerate(lines):
        line = line.strip()
        if not line:
            continue
        # 解析格式1：00:00:00 主持人：内容
        if "：" in line:
            if len(line.split("：")) >= 2:
                left, content = line.split("：", 1)
                # 提取时间和发言人
                if " " in left:
                    time_part, speaker = left.split(" ", 1)
                else:
                    time_part = f"00:{idx:02d}:00"  # 模拟时间
                    speaker = left
                speech_list.append({
                    "time": time_part,
                    "speaker": speaker,
                    "content": content
                })
        else:
            # 无分隔符，默认主持人发言
            speech_list.append({
                "time": f"00:{idx:02d}:00",
                "speaker": "未知发言人",
                "content": line
            })
    return speech_list

# 测试
if __name__ == '__main__':
    test_text = "00:00:00 主持人：测试会议内容\n技术负责人：需要产品侧提供测试用例"
    print(parse_speech(test_text))
