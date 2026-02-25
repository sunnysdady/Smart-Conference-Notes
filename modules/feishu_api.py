def create_feishu_doc(title: str, content: str) -> Dict[str, Any]:
    """
    修复 document_id 报错，使用兼容的飞书文档创建接口
    """
    if not FEISHU_CONFIG["TENANT_ACCESS_TOKEN"]:
        get_tenant_access_token()
    
    # 1. 使用更兼容的 drive/v1/files 接口创建文档
    create_url = "https://open.feishu.cn/open-apis/drive/v1/files/create"
    headers = {
        "Authorization": f"Bearer {FEISHU_CONFIG['TENANT_ACCESS_TOKEN']}",
        "Content-Type": "application/json"
    }
    create_data = {
        "title": title,
        "type": "docx",
        "folder_token": ""  # 可选：指定文件夹
    }
    
    response = requests.post(create_url, headers=headers, json=data, timeout=30)
    response.raise_for_status()
    create_result = response.json()
    
    if create_result.get("code") != 0:
        raise Exception(f"创建文档失败：{create_result.get('msg')}")
    
    # 🌟 修复点：新接口返回的是 file_token，而不是 document_id
    file_token = create_result["data"]["file_token"]
    doc_id = file_token  # 用 file_token 作为 doc_id
    
    # 2. 转换 Markdown 为飞书文档节点（逻辑不变）
    def md_to_feishu_nodes(md_content: str) -> list:
        # ... 保持原有逻辑 ...
    
    # 3. 写入内容，使用新的 doc_id
    content_url = f"https://open.feishu.cn/open-apis/docx/v1/documents/{doc_id}/content"
    content_data = {
        "requests": [{"insert": {"location": {"index": 0}, "nodes": md_to_feishu_nodes(content)}}]
    }
    requests.patch(content_url, headers=headers, json=content_data, timeout=30)
    
    # 拼接文档链接
    doc_url = f"https://www.feishu.cn/docs/d/{doc_id}"
    return {"doc_id": doc_id, "doc_url": doc_url, "title": title}
