import os
import requests
import json
from pathlib import Path
from tqdm import tqdm
from functools import wraps
import time
import logging
import sys

class ModelDownloadError(Exception):
    """模型下载异常"""
    pass

def retry(max_retries=3, delay=1):
    """重试装饰器
    
    Args:
        max_retries: 最大重试次数
        delay: 重试间隔（秒）
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            retries = 0
            last_exception = None
            
            while retries < max_retries:
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    last_exception = e
                    retries += 1
                    if retries < max_retries:
                        logging.warning(f"第 {retries} 次尝试失败: {str(e)}")
                        logging.info(f"等待 {delay} 秒后重试...")
                        time.sleep(delay)
                    else:
                        logging.error(f"已达到最大重试次数 {max_retries}")
                        raise ModelDownloadError(f"下载失败: {str(last_exception)}")
            return None
        return wrapper
    return decorator

class ModelDownloader:
    def __init__(self):
        # 获取当前文件所在目录
        current_dir = Path(__file__).parent
        # 读取模型配置
        with open(current_dir / 'model_config.json', 'r', encoding='utf-8') as f:
            self.model_config = json.load(f)
        # 设置模型目录
        self.model_path = current_dir.parent / 'models'
        self.model_path.mkdir(parents=True, exist_ok=True)
        print(f"模型根目录: {self.model_path}")
        
    @retry(max_retries=3, delay=2)
    def download_file(self, url, filename, model_name):
        """下载文件到models目录下的模型子目录
        
        Args:
            url: 下载链接
            filename: 保存的文件名
            model_name: 模型名称，用于创建子目录
        
        Returns:
            bool: 下载是否成功
            
        Raises:
            ModelDownloadError: 下载失败时抛出
        """
        # 创建模型子目录
        model_dir = self.model_path / model_name
        model_dir.mkdir(parents=True, exist_ok=True)
        target_path = model_dir / filename
        
        print(f"\n检查文件: {filename}")
        
        # 检查文件是否已存在
        if target_path.exists():
            print(f"✓ 文件已存在: {target_path}")
            return True
        
        print(f"开始下载: {url}")
        try:
            # 设置请求头，模拟浏览器行为
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
            }
            
            # 发起请求
            response = requests.get(url, stream=True, headers=headers, timeout=30)
            response.raise_for_status()
            
            # 获取文件大小
            total_size = int(response.headers.get('content-length', 0))
            
            # 使用tqdm显示下载进度
            with open(target_path, 'wb') as f, tqdm(
                desc=filename,
                total=total_size,
                unit='iB',
                unit_scale=True,
                unit_divisor=1024,
            ) as pbar:
                for data in response.iter_content(chunk_size=1024):
                    size = f.write(data)
                    pbar.update(size)
            
            print(f"✓ 文件 {filename} 下载完成")
            return True
            
        except Exception as e:
            print(f"✗ 下载 {filename} 时发生错误: {str(e)}")
            # 删除可能下载了一半的文件
            if target_path.exists():
                target_path.unlink()
            raise ModelDownloadError(f"下载文件 {filename} 失败: {str(e)}")
    
    def download_sense_voice_model(self):
        """下载SenseVoice模型文件
        
        Returns:
            bool: 下载是否成功
            
        Raises:
            ModelDownloadError: 下载失败时抛出
        """
        print("\n=== 开始检查 SenseVoice 模型文件 ===")
        model_name = "SenseVoiceSmall"
        model_files = self.model_config.get(model_name, {})
        
        for filename, info in model_files.items():
            print(f"\n处理文件: {filename}")
            if not self.download_file(info['url'], filename, model_name):
                raise ModelDownloadError(f"文件 {filename} 下载失败")
        
        print(f"\n✓ 所有模型文件已下载到: {self.model_path / model_name}")
        return True