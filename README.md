# AIAssistant
智能助手

## windows下的麦克风和音频输出设置

1. **安装 VB-Audio Virtual Cable**  
   - 下载并安装官方驱动，系统会新增 “CABLE Input” 和 “CABLE Output” 两条虚拟线路。

2. **将物理麦克风路由到虚拟线**  
   - 打开 **声音** → **录制** → 选中你的物理麦克风 → **属性** → **聆听** → 在“将此设备的播放通过”下拉中选择 **CABLE Input (VB-Audio Virtual Cable)** → 点击**确定**。  
   - 对着麦克风说话时，**CABLE Input** 的音量指示会随之波动。

3. **选择支持双工的 Hands-Free 输出**  
   - 打开 **声音** → **播放** → 将 **Hands-Free AG Audio** 设备设为默认输出。  
   - 播放任意视频或音频时，**CABLE Input** 会同时捕获到 TTS/系统回放和麦克风输入，验证配置成功。 