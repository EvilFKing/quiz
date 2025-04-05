# 测试题一：
# 本地实现的环境配置
1. 安装Docker
2. 安装Python3.11+
3. 拉取代码到open-interpreter主目录下
4. 安装requirements

# 配置修改方式一
# 手动修改代码（当前实现方式）
1. 修改interpreter/terminal_interface/profiles/defaults/default.yaml 中的model,api_key,api_base相关配置
   ![1](https://github.com/user-attachments/assets/4891d71a-1c9e-4beb-8954-c62c5c39302a)

3. 修改interpreter/core/async_core.py中的DEFAULT_HOST地址为0.0.0.0
# 配置修改方式二
# http请求修改
1. http://localhost:8000/settings

### 注意事项
1. docker容器中不要禁用网络，否则会导致无法访问到容器内部的服务
2. 默认端口8000请注意不要被占用
3. sandbox可以配置资源限制，过低将导致反应速度变慢

### Docker沙箱环境

1. **安全隔离**
   - 使用Docker容器实现代码执行环境隔离
   - 限制CPU和内存使用
   - 进程数量限制（最多100个进程）
   - 临时文件系统挂载，确保文件系统安全

2. **资源管理**
   - 自动构建Docker镜像
   - 容器生命周期管理（创建、启动、停止）
   - 容器状态检查和监控

### WebSocket通信

1. **可靠连接**
   - 自动重连机制
   - 心跳检测
   - 超时保护
   - 连接状态监控

2. **消息处理**
   - 支持JSON格式消息
   - 实时消息流处理
   - 完整的错误处理机制
   - 支持异步通信

### 日志系统

- 详细的操作日志记录
- 可配置的日志级别（支持DEBUG模式）
- 异常信息捕获和记录

###

- **web界面**
   - 提供一个web界面，用于查看日志、配置参数、查看状态等

## 配置说明

### Docker沙箱配置

```python
DockerSandbox(
    image_name="sandbox-image",    # Docker镜像名称
    cpu_limit="2",               # CPU限制
    memory_limit="1024m",        # 内存限制
    timeout=30,                  # 执行超时时间
    host_port=8000,              # WebSocket服务端口
    max_retries=10,              # 最大重试次数
    retry_delay=2,               # 重试延迟时间
    debug=False                  # 调试模式
)
```

### WebSocket客户端配置

```python
WebSocketClient(
    websocket_url="ws://localhost:8000/",
    max_retries=10,              # 最大重试次数
    retry_delay=2,               # 重试延迟时间
    timeout=30,                  # 超时时间
    debug=False                  # 调试模式
)
```

## 代码结构

### 主要模块

1. **sandbox.py**
   - Docker沙箱环境管理
   - 容器生命周期控制
   - 资源限制实现

2. **websocket_client.py**
   - WebSocket通信实现
   - 消息处理逻辑
   - 连接管理

## 错误处理

1. **容器管理**
   - 镜像构建失败处理
   - 容器启动异常处理
   - 资源限制异常处理

2. **WebSocket通信**
   - 连接断开处理
   - 消息发送失败处理
   - 超时处理
   - JSON解析错误处理

## 使用说明

1. 初始化沙箱环境：
   ```python
   sandbox = DockerSandbox()
   ```

2. 构建Docker镜像：
   ```python
   sandbox.build_image()
   ```

3. 启动容器：
   ```python
   sandbox.start_container()
   ```

4. 运行代码：
   ```python
   response = await sandbox.run_interpreter("print('Hello, World!')")
   ```

5. 停止容器：
   ```python
   sandbox.stop_container()
   ```

# 启动方式

- monitor webui界面启动
1. python monitor.py

- interpreter启动
1. python main.py --interactive


# 测试题二
1.根据yaml文件来配置多个llm,并使用websocket连接它们。
