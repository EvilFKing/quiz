import logging
import json
import asyncio
import time
from typing import Dict, Any, Optional
import websockets

# 设置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("websocket_client")

class WebSocketClient:
    """WebSocket客户端类，用于处理与服务器的通信"""
    
    def __init__(self, 
                 websocket_url: str,
                 max_retries: int = 10,
                 retry_delay: int = 2,
                 timeout: int = 30,
                 debug: bool = False):
        """初始化WebSocket客户端
        
        参数:
            websocket_url: WebSocket服务器URL
            max_retries: 最大重试次数
            retry_delay: 重试延迟（秒）
            timeout: 超时时间（秒）
            debug: 是否启用调试模式
        """
        self.websocket_url = websocket_url
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self.timeout = timeout
        self.debug = debug
        
        if debug:
            logger.setLevel(logging.DEBUG)
    
    async def connect(self, retries: int = None) -> Optional[websockets.WebSocketClientProtocol]:
        """连接到WebSocket服务器
        
        参数:
            retries: 重试次数，默认使用self.max_retries
            
        返回:
            WebSocket连接对象，如果连接失败则返回None
        """
        if retries is None:
            retries = self.max_retries
            
        for attempt in range(retries):
            try:
                logger.info(f"尝试连接WebSocket: {self.websocket_url} (尝试 {attempt+1}/{retries})")
                websocket = await websockets.connect(self.websocket_url)
                logger.info("WebSocket连接成功")
                return websocket
            except Exception as e:
                logger.error(f"WebSocket连接失败: {e}")
                if attempt < retries - 1:
                    wait_time = self.retry_delay * (attempt + 1)
                    logger.info(f"等待 {wait_time} 秒后重试...")
                    time.sleep(wait_time)
                else:
                    logger.error(f"WebSocket连接失败，已达到最大重试次数: {retries}")
                    return None
    
    async def send_message(self, message: str) -> Dict[str, Any]:
        """发送消息到WebSocket服务器
        
        参数:
            message: 用户消息
            
        返回:
            包含执行结果的字典
        """
        websocket = None
        try:
            # 连接WebSocket
            websocket = await self.connect()
            if not websocket:
                return {
                    "success": False,
                    "error": "无法连接到WebSocket服务"
                }
            
            # 发送用户消息
            messages = [
                {"auth": True},
                {"role": "user", "type": "message", "start": True},
                {"role": "user", "type": "message", "content": message},
                {"role": "user", "type": "message", "end": True}
            ]
            
            try:
                for msg in messages:
                    if self.debug:
                        logger.debug(f"Sending message: {msg}")
                    await websocket.send(json.dumps(msg))
            except websockets.exceptions.ConnectionClosed:
                logger.error("WebSocket连接在发送消息时关闭")
                return {
                    "success": False,
                    "error": "WebSocket连接在发送消息时关闭"
                }
            
            # 接收响应
            responses = []
            current_response = ""
            connection_active = True
            message_complete = False
            start_time = time.time()
            last_activity_time = time.time()
            
            while connection_active:
                try:
                    # 添加超时保护
                    current_time = time.time()
                    if current_time - start_time > self.timeout:
                        logger.warning(f"接收消息超时 ({self.timeout}秒)")
                        break
                    
                    # 检查最后活动时间
                    if current_time - last_activity_time > 10:  # 10秒无活动则发送心跳
                        try:
                            await websocket.ping()
                            last_activity_time = current_time
                        except Exception as e:
                            logger.error(f"发送心跳失败: {e}")
                            break
                    
                    # 设置接收超时
                    try:
                        response = await asyncio.wait_for(websocket.recv(), timeout=5.0)
                        last_activity_time = time.time()  # 更新最后活动时间
                        response_data = json.loads(response)
                        responses.append(response_data)
                        
                        # 实时处理消息内容
                        if "content" in response_data:
                            current_response = response_data["content"]
                            print(current_response, end="", flush=True)
                        
                        # 检查消息完成状态
                        if response_data.get("type") == "status":
                            if response_data.get("content") == "complete":
                                message_complete = True
                                
                        # 消息完成时不关闭连接，保持连接状态以支持后续对话
                        if message_complete:
                            break  # 仅退出当前消息的接收循环
                        
                    except asyncio.TimeoutError:
                        continue
                    except json.JSONDecodeError as e:
                        logger.error(f"JSON解析错误: {e}")
                        responses.append({"text": response})
                        print(response, end="", flush=True)
                    except websockets.exceptions.ConnectionClosed:
                        logger.error("WebSocket连接已关闭")
                        return {
                            "success": False,
                            "error": "WebSocket连接已关闭"
                        }
                    except Exception as e:
                        logger.error(f"接收消息时出错: {e}")
                        connection_active = False
                        break
                        
                except Exception as e:
                    logger.error(f"消息处理循环出错: {e}")
                    connection_active = False
                    break
            
            # 返回完整响应
            full_response = ""
            for resp in responses:
                if "content" in resp:
                    full_response += resp["content"]
                elif "text" in resp:
                    full_response += resp["text"]
            
            return {
                "success": True,
                "stdout": full_response,
                "complete": True,
                "responses": responses
            }
            
        except websockets.exceptions.ConnectionClosed:
            logger.error("WebSocket连接已关闭")
            return {
                "success": False,
                "error": "WebSocket连接已关闭"
            }
        except Exception as e:
            logger.error(f"WebSocket通信出错: {e}")
            return {
                "success": False,
                "error": str(e)
            }
        finally:
            # 在finally块中关闭WebSocket连接
            if websocket:
                try:
                    # 只有在消息处理完成或发生错误时才关闭连接
                    if message_complete or not connection_active:
                        await websocket.close()
                        logger.debug("WebSocket连接已正常关闭")
                except Exception as e:
                    logger.error(f"关闭WebSocket连接时出错: {e}")
            
            # WebSocket连接清理完成
            logger.debug("WebSocket资源已清理完成")
    
    async def check_available(self) -> bool:
        """检查WebSocket服务是否可用
        
        返回:
            WebSocket服务是否可用
        """
        try:
            # 尝试连接WebSocket，设置较短的超时时间
            websocket = await websockets.connect(self.websocket_url, timeout=3)
            await websocket.close()
            logger.debug("WebSocket服务可用")
            return True
        except Exception as e:
            logger.debug(f"WebSocket服务不可用: {e}")
            return False