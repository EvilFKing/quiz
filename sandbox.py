import os
import subprocess
import logging
import time
from typing import Dict, Any
from websocket_client import WebSocketClient

# 设置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("sandbox")


class DockerSandbox:
    """Docker沙箱环境，用于安全地运行代码，并通过WebSocket连接与容器通信"""
    
    def __init__(self, 
                 image_name: str = "sandbox-image",
                 cpu_limit: str = "2",
                 memory_limit: str = "1024m",
                 timeout: int = 30,
                 dockerfile_path: str = None,
                 host_port: int = 8000,
                 max_retries: int = 10,
                 retry_delay: int = 2,
                 debug: bool = False,
                 # 新增权限控制选项
                 user_id: str = None,  # 容器内用户ID映射
                 group_id: str = None,  # 容器内组ID映射
                 network_mode: str = "bridge",  # 网络模式: bridge/host/none
                 cap_drop: list = None,  # 需要移除的Linux capabilities
                 cap_add: list = None,    # 需要添加的Linux capabilities
                 read_only: bool = False,  # 是否启用只读文件系统
                 volumes: dict = None,    # 挂载卷配置 {host_path: container_path}
                 seccomp_profile: str = None):  # 系统调用限制配置文件路径
        """初始化Docker沙箱
        
        参数:
            image_name: Docker镜像名称
            cpu_limit: CPU使用限制
            memory_limit: 内存使用限制
            timeout: 运行超时时间（秒）
            dockerfile_path: Dockerfile路径，默认使用项目根目录
            host_port: 主机上的WebSocket服务器端口
            debug: 是否启用调试模式
            user_id: 容器内进程的用户ID映射
            group_id: 容器内进程的组ID映射
            network_mode: 网络模式(bridge/host/none)
            cap_drop: 需要移除的Linux capabilities列表
            cap_add: 需要添加的Linux capabilities列表
            read_only: 是否启用只读文件系统
            volumes: 挂载卷配置字典
            seccomp_profile: 系统调用限制配置文件路径
        """
        self.image_name = image_name
        self.cpu_limit = cpu_limit
        self.memory_limit = memory_limit
        self.timeout = timeout
        self.container_id = None
        self.host_port = host_port
        self.debug = debug
        
        # 初始化权限控制选项
        self.user_id = user_id
        self.group_id = group_id
        self.network_mode = network_mode
        self.cap_drop = cap_drop if cap_drop else ["ALL"]  # 默认移除所有capabilities
        self.cap_add = cap_add if cap_add else []  # 默认不添加任何capabilities
        self.read_only = read_only
        self.volumes = volumes if volumes else {}
        self.seccomp_profile = seccomp_profile
        
        # 设置日志级别
        if debug:
            logger.setLevel(logging.DEBUG)
        
        # 获取项目根目录的Dockerfile路径
        if dockerfile_path is None:
            current_dir = os.path.dirname(os.path.abspath(__file__))
            self.dockerfile_path = os.path.join(os.path.dirname(current_dir), "Dockerfile")
        else:
            self.dockerfile_path = dockerfile_path
        
        # 初始化WebSocket客户端
        websocket_url = f"ws://localhost:{host_port}/"
        self.websocket_client = WebSocketClient(
            websocket_url=websocket_url,
            max_retries=max_retries,
            retry_delay=retry_delay,
            timeout=timeout,
            debug=debug
        )
        
        logger.info(f"Using Dockerfile at: {self.dockerfile_path}")
    
    def build_image(self) -> bool:
        """构建Docker镜像
        
        返回:
            是否成功构建
        """
        try:
            logger.info(f"Building Docker image: {self.image_name}")
            dockerfile_dir = os.path.dirname(self.dockerfile_path)
            
            build_cmd = [
                "docker", "build", 
                "-t", self.image_name,
                "-f", self.dockerfile_path,
                dockerfile_dir
            ]
            
            logger.info(f"Running command: {' '.join(build_cmd)}")
            result = subprocess.run(
                build_cmd,
                check=True,
                capture_output=True,
                text=True
            )
            
            logger.info(f"Build output: {result.stdout}")
            return True
        
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to build image: {e}")
            logger.error(f"Build error output: {e.stderr}")
            return False
        
        except Exception as e:
            logger.error(f"Error building image: {e}")
            return False
 
    def check_container_exists(self) -> bool:
        """检查容器是否存在并运行
        
        返回:
            容器是否存在并运行
        """
        try:
            # 检查是否有正在运行的容器
            if self.container_id:
                # 检查指定ID的容器
                cmd = ["docker", "ps", "-q", "-f", f"id={self.container_id}", "-f", "status=running"]
            else:
                # 检查基于镜像名称的容器
                cmd = ["docker", "ps", "-q", "-f", f"ancestor={self.image_name}", "-f", "status=running"]
            
            result = subprocess.run(
                cmd,
                check=False,
                capture_output=True,
                text=True
            )
            
            container_ids = result.stdout.strip().split('\n')
            container_ids = [cid for cid in container_ids if cid]  # 过滤空行
            
            if container_ids:
                # 如果找到了容器，保存第一个容器ID
                self.container_id = container_ids[0]
                logger.debug(f"找到运行中的容器: {self.container_id}")
                return True
            else:
                logger.debug("没有找到运行中的容器")
                return False
                
        except Exception as e:
            logger.error(f"检查容器时出错: {e}")
            return False
    
    def start_container(self) -> bool:
        """启动一个新的容器
        
        返回:
            是否成功启动容器
        """
        try:
            # 创建一个Docker容器，运行interpreter服务器
            command = [
                "docker", "run", "-d",  # 后台运行
                "-p", f"{self.host_port}:8000",
                "--cpus", self.cpu_limit,
                "--memory", self.memory_limit,
                "--pids-limit=100",  # 限制进程数
            ]
            
            # 添加用户和组ID映射
            if self.user_id:
                command.extend(["--user", self.user_id])
            if self.group_id:
                command.extend(["--group-add", self.group_id])
                
            # 添加网络模式配置
            command.extend(["--network", self.network_mode])
            
            # 添加capabilities控制
            for cap in self.cap_drop:
                command.extend(["--cap-drop", cap])
            for cap in self.cap_add:
                command.extend(["--cap-add", cap])
                
            # 添加文件系统权限控制
            if self.read_only:
                command.append("--read-only")
            
            # 添加必要的临时文件系统挂载点
            command.extend([
                "--tmpfs", "/tmp:exec,mode=777",
                "--tmpfs", "/var/tmp:exec,mode=777",
                "--tmpfs", "/run:exec,mode=777"
            ])
            
            # 添加自定义卷挂载
            for host_path, container_path in self.volumes.items():
                command.extend(["-v", f"{host_path}:{container_path}"])
                
            # 添加系统调用限制配置
            if self.seccomp_profile:
                command.extend(["--security-opt", f"seccomp={self.seccomp_profile}"])
            
            # 添加镜像名称
            command.append(self.image_name)
            
            logger.info(f"启动容器: {' '.join(command)}")
            
            result = subprocess.run(
                command,
                check=True,
                capture_output=True,
                text=True
            )
            
            # 获取容器ID
            self.container_id = result.stdout.strip()
            logger.info(f"容器启动成功，ID: {self.container_id}")
            
            # 等待容器内的服务启动
            time.sleep(2)
            return True
            
        except subprocess.CalledProcessError as e:
            logger.error(f"启动容器失败: {e}")
            logger.error(f"错误输出: {e.stderr}")
            return False
        except Exception as e:
            logger.error(f"启动容器时出错: {e}")
            return False
    
    def stop_container(self) -> bool:
        """停止正在运行的容器
        
        返回:
            是否成功停止容器
        """
        if not self.container_id:
            logger.info("没有正在运行的容器需要停止")
            return True
            
        try:
            logger.info(f"正在停止容器: {self.container_id}")
            result = subprocess.run(
                ["docker", "stop", self.container_id],
                check=True,
                capture_output=True,
                text=True
            )
            
            logger.info(f"容器已停止: {self.container_id}")
            self.container_id = None
            return True
            
        except subprocess.CalledProcessError as e:
            logger.error(f"停止容器失败: {e}")
            logger.error(f"错误输出: {e.stderr}")
            return False
        except Exception as e:
            logger.error(f"停止容器时出错: {e}")
            return False
    
    async def check_websocket_available(self) -> bool:
        """检查WebSocket服务是否可用
        
        返回:
            WebSocket服务是否可用
        """
        return await self.websocket_client.check_available()
    
    async def run_interpreter(self, message: str) -> Dict[str, Any]:
        """在沙箱中运行Open Interpreter
        
        参数:
            message: 用户消息
            
        返回:
            包含执行结果的字典
        """        
        try:
            response = await self.websocket_client.send_message(message)
            return response
            
        except Exception as e:
            logger.error(f"运行interpreter时出错: {e}")
            return {
                "success": False,
                "error": str(e)
            }