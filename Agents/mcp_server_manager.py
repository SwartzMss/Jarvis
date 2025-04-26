from typing import Dict, List, Optional
import yaml
from pathlib import Path
from agents.mcp import MCPServerStdio, MCPUtil

class MCPServerManager:
    def __init__(self):
        self._servers: Dict[str, MCPServerStdio] = {}
        self._tools: Dict[str, List[dict]] = {}
        self._config: Dict = {}
        
    async def load_config(self, config_path: str = None) -> None:
        """加载配置文件"""
        if config_path is None:
            config_path = Path(__file__).parent / "mcp_server_config.yaml"
            
        print(f"正在加载 MCP server 配置文件: {config_path}")
        with open(config_path, 'r', encoding='utf-8') as f:
            self._config = yaml.safe_load(f)
        print("配置文件加载完成")
            
    async def initialize_servers(self) -> None:
        """根据配置文件初始化所有 MCP server"""
        if not self._config:
            await self.load_config()
            
        print("\n开始初始化 MCP servers...")
        for server_name, server_config in self._config.get('servers', {}).items():
            print(f"\n正在初始化 {server_name} server...")
            print(f"命令: {server_config['params']['command']} {' '.join(server_config['params']['args'])}")
            
            server = MCPServerStdio(
                name=server_name,
                params=server_config.get('params', {}),
                cache_tools_list=server_config.get('cache_tools_list', True)
            )
            try:
                await self.add_server(server_name, server)
                print(f"✓ {server_name} server 初始化成功")
            except Exception as e:
                print(f"✗ {server_name} server 初始化失败: {e}")
                continue
                
        print("\n所有 MCP servers 初始化完成")
            
    async def add_server(self, name: str, server: MCPServerStdio) -> None:
        """添加一个新的 MCP server"""
        try:
            print(f"正在连接 {name} server...")
            await server.connect()
            self._servers[name] = server
            # 获取该 server 的工具列表
            print(f"正在获取 {name} server 的工具列表...")
            tools = await server.list_tools()
            self._tools[name] = tools
            print(f"已获取 {name} server 的 {len(tools)} 个工具")
        except Exception as e:
            print(f"Error adding server {name}: {e}")
            if name in self._servers:
                del self._servers[name]
            raise
        
    def get_server(self, name: str) -> Optional[MCPServerStdio]:
        """获取指定名称的 server"""
        return self._servers.get(name)
        
    async def get_all_tools(self) -> List:
        """获取所有 server 的工具列表"""
        # 使用 MCPUtil 获取所有工具
        servers = list(self._servers.values())
        print("\n正在获取所有 server 的工具列表...")
        tools_list = await MCPUtil.get_all_function_tools(servers, convert_schemas_to_strict=False)
        print(f"已获取 {len(tools_list)} 个工具")
        return tools_list
        
    async def get_server_tools(self, server_name: str) -> Optional[List[dict]]:
        """获取指定 server 的工具列表"""
        return self._tools.get(server_name)
        
    async def refresh_tools(self) -> None:
        """刷新所有 server 的工具列表"""
        print("\n正在刷新所有 server 的工具列表...")
        for name, server in self._servers.items():
            try:
                print(f"正在刷新 {name} server 的工具列表...")
                tools = await server.list_tools()
                self._tools[name] = tools
                print(f"已刷新 {name} server 的 {len(tools)} 个工具")
            except Exception as e:
                print(f"Error refreshing tools for server {name}: {e}")
            
    async def close(self) -> None:
        """关闭所有 server 连接"""
        print("\n正在关闭所有 MCP servers...")
        for name, server in list(self._servers.items()):
            try:
                print(f"正在关闭 {name} server...")
                await server.cleanup()
                print(f"✓ {name} server 已关闭")
            except Exception as e:
                print(f"✗ 关闭 {name} server 时出错: {e}")
            finally:
                if name in self._servers:
                    del self._servers[name]
        self._tools.clear()
        print("所有 MCP servers 已关闭")

# 创建全局实例
mcp_server_manager = MCPServerManager() 