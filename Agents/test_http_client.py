import requests
import json

def test_chat():
    """测试与服务器的聊天功能"""
    # 服务器地址
    url = "http://127.0.0.1:8002/chat"
    
    # 准备请求数据
    data = {
        "content": "1+3=?"
    }
    
    try:
        # 发送POST请求
        response = requests.post(url, json=data)
        
        # 检查响应状态
        response.raise_for_status()
        
        # 解析响应
        result = response.json()
        print("服务器响应:", result["response"])
        
    except requests.exceptions.RequestException as e:
        print(f"请求出错: {e}")
    except json.JSONDecodeError as e:
        print(f"解析响应出错: {e}")

if __name__ == "__main__":
    print("开始测试HTTP客户端...")
    test_chat() 