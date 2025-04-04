import sys
import argparse
import json
import os
import signal
import subprocess
import locale
import asyncio
from sandbox import DockerSandbox
import time

# 检查和安装所需的库
def ensure_dependencies():
    try:
        import websockets
    except ImportError:
        print("正在安装必要的库: websockets...")
        try:
            subprocess.check_call([sys.executable, "-m", "pip", "install", "websockets"])
            print("websockets 安装成功！")
        except Exception as e:
            print(f"安装websockets失败: {e}")
            print("请手动运行: pip install websockets")
            sys.exit(1)

# 确保依赖项已安装
ensure_dependencies()

# 设置默认编码为UTF-8
if sys.platform == 'win32':
    # 尝试设置控制台编码为UTF-8（Windows）
    os.system('chcp 65001 > NUL')
    
    # 设置Python的默认编码
    if hasattr(sys, 'setdefaultencoding'):
        sys.setdefaultencoding('utf-8')
    
    # 设置标准输出/错误的编码
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace', line_buffering=True)
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace', line_buffering=True)

# 打印当前环境编码
print(f"默认编码: {sys.getdefaultencoding()}")
print(f"文件系统编码: {sys.getfilesystemencoding()}")
print(f"区域设置: {locale.getpreferredencoding()}")


def signal_handler(sig, frame):
    """处理Ctrl+C信号"""
    print("\n\n程序被中断，正在退出...")
    sys.exit(0)


def check_image_exists(image_name):
    """检查Docker镜像是否存在"""
    try:
        # 显式设置encoding参数为utf-8
        result = subprocess.run(
            ["docker", "images", "-q", image_name],
            capture_output=True,
            text=True,
            encoding='utf-8',
            errors='replace',
            check=False
        )
        return bool(result.stdout.strip())
    except Exception as e:
        print(f"检查Docker镜像时出错: {e}")
        return False


def main():
    """主函数，处理用户输入并将其传递给Docker沙箱"""
    # 设置信号处理
    signal.signal(signal.SIGINT, signal_handler)
    
    parser = argparse.ArgumentParser(description="与Docker沙箱中的Open Interpreter交互")
    parser.add_argument("--build", help="强制重新构建Docker镜像", action="store_true")
    parser.add_argument("--message", help="要发送给Interpreter的消息")
    parser.add_argument("--interactive", help="进入交互模式", action="store_true")
    parser.add_argument("--cpu", help="CPU限制", default="0.5")
    parser.add_argument("--memory", help="内存限制", default="256m")
    parser.add_argument("--timeout", help="执行超时时间（秒）", type=int, default=120)
    parser.add_argument("--image", help="指定Docker镜像名称", default="sandbox-image")
    parser.add_argument("--port", help="指定WebSocket服务器端口", type=int, default=8000)
    parser.add_argument("--debug", help="启用调试模式", action="store_true")
    
    args = parser.parse_args()
    
    try:
        # 创建沙箱实例
        sandbox = DockerSandbox(
            image_name=args.image,
            cpu_limit=args.cpu,
            memory_limit=args.memory,
            timeout=args.timeout,
            host_port=args.port,
            debug=args.debug
        )
        
        # 检查镜像是否存在，不存在则构建
        image_exists = check_image_exists(args.image)
        if args.build or not image_exists:
            if args.build:
                print(f"正在强制重新构建Docker镜像: {args.image}...")
            else:
                print(f"Docker镜像 {args.image} 不存在，正在构建...")
            
            if not sandbox.build_image():
                print("构建Docker镜像失败，退出。", file=sys.stderr)
                sys.exit(1)
            
            print("Docker镜像构建成功！")
        else:
            print(f"使用现有Docker镜像: {args.image}")
        
        # 处理单条消息
        if args.message:
            print(f"发送消息到Docker沙箱: {args.message}")
            # 创建事件循环
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
            # 运行异步函数
            result = loop.run_until_complete(sandbox.run_interpreter(args.message))
            loop.close()
            
            if result["success"]:
                if not result.get("stdout"):
                    print("\n(沙箱执行成功，但没有输出)")
            else:
                print("\n--- 执行错误 ---")
                print(result.get("error", "未知错误"))
                if result.get("stderr"):
                    print(result["stderr"])
        
        # 交互模式
        elif args.interactive or not (args.message or args.build):
            print("\n=== Docker沙箱中的Open Interpreter交互模式 ===")
            print("输入 'exit' 或 'quit' 退出，按Ctrl+C中断。")
            print("示例命令: '计算1+1'，'帮我画一个圆形'\n")
            
            while True:
                try:
                    # 获取用户输入
                    user_input = input("\033[1m>>> \033[0m")
                    
                    # 检查退出命令
                    if user_input.lower() in ["exit", "quit", "q", "退出"]:
                        print("退出交互模式。")
                        break
                    
                    if not user_input.strip():
                        continue
                    
                    # 发送消息到沙箱
                    print("发送中...\n")
                    try:
                        # 创建事件循环
                        loop = asyncio.new_event_loop()
                        asyncio.set_event_loop(loop)
                        
                        # 运行异步函数
                        result = loop.run_until_complete(sandbox.run_interpreter(user_input))
                        loop.close()
                        
                        if result["success"]:
                            if not result.get("stdout"):
                                print("(沙箱执行成功，但没有输出)")
                        else:
                            print("\n--- 执行错误 ---")
                            error_msg = result.get("error", "未知错误")
                            print(f"错误: {error_msg}")
                            if result.get("stderr"):
                                print("详细错误信息:")
                                print(result["stderr"])
                        
                        # 消息间隔，避免过快发送请求
                        time.sleep(1)
                    except Exception as e:
                        print(f"\n发送消息出错: {e}")
                        print("正在尝试恢复...")
                        time.sleep(3)  # 出错后等待更长时间
                    
                except KeyboardInterrupt:
                    choice = input("\n\n是否要退出程序? (y/n): ")
                    if choice.lower() in ['y', 'yes', '是']:
                        print("退出程序。")
                        break
                    print("继续执行。")
                except Exception as e:
                    print(f"发生错误: {e}")
                    print("尝试继续执行...")
        
        else:
            # 显示帮助信息
            parser.print_help()
    
    except Exception as e:
        print(f"程序执行过程中发生错误: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()