# Jarvis AI Assistant (Jarvis 智能助手)

Jarvis 是一个基于 Python 的语音助手，集成了语音识别、文本转语音(TTS)以及多种任务管理代理。它由以下模块构成：

- **TTS** – FastAPI 服务，使用 Microsoft Edge TTS 将文字转成语音
- **STT** – 接收麦克风音频，检测唤醒词并使用 SenseVoice 进行语音识别
- **Agents** – 实现主要的对话循环以及多种任务相关的代理（文件系统、网络搜索、表格操作等）
- **MCP** – 为代理提供文件管理、Excel 自动化等小服务
- **Service** – 其他服务，如 `Service/face_recognition` 中的人脸识别示例

## 快速开始
1. 安装 Python 3.10+，并创建虚拟环境
2. 安装各模块依赖
   ```bash
   pip install -r Agents/requirements.txt
   pip install -r STT/requirements.txt
   pip install -r TTS/requirements.txt
   ```
3. (可选) 将 `.env.example` 复制为 `.env`，根据需求修改配置
4. 启动 TTS 服务
   ```bash
   python TTS/main.py
   ```
5. 启动语音识别端(STT)
   ```bash
   python STT/main.py
   ```
6. 运行主对话界面
   ```bash
   python Agents/main.py
   ```

日常使用时可以直接打字或对着麦克风说话，结果会通过 TTS 转成语音播放

### Windows 下麦克风和音频输出配置
1. 安装 **VB-Audio Virtual Cable**，安装后系统会多出 `CABLE Input` 和 `CABLE Output` 设备
2. 将物理麦克风路由至虚拟线：开启 **声音 → 录制**，选中麦克风设备，点 **属性** → **听受**，在“将此设备的播放通过”中选择 **CABLE Input (VB-Audio Virtual Cable)**
3. 选择支持双工的输出设备：在 **声音 → 播放** 中将 **Hands-Free AG Audio** 设置为默认输出，此时系统播放和麦克风输入都会达到 `CABLE Input`

## License

This project is released under the MIT License.
