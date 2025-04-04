import unittest
import subprocess
import json
import os
import time
from sandbox import DockerSandbox

class TestDockerSandbox(unittest.TestCase):
    """测试DockerSandbox类"""
    
    @classmethod
    def setUpClass(cls):
        """在所有测试之前运行一次"""
        # 检查Docker是否可用
        try:
            subprocess.run(["docker", "--version"], check=True, capture_output=True)
        except (subprocess.CalledProcessError, FileNotFoundError):
            raise unittest.SkipTest("Docker is not available or not running")
        
        # 获取项目根目录的Dockerfile路径
        current_dir = os.path.dirname(os.path.abspath(__file__))
        dockerfile_path = os.path.join(os.path.dirname(current_dir), "Dockerfile")
        
        # 构建测试镜像
        print(f"Building test Docker image using Dockerfile at: {dockerfile_path}")
        result = subprocess.run(
            ["docker", "build", "-t", "sandbox-test-image", "-f", dockerfile_path, os.path.dirname(dockerfile_path)],
            check=False,
            capture_output=True
        )
        if result.returncode != 0:
            raise unittest.SkipTest(f"Failed to build Docker image: {result.stderr.decode()}")
    
    def setUp(self):
        """每个测试前运行"""
        self.sandbox = DockerSandbox(image_name="sandbox-test-image")
    
    def test_simple_code_execution(self):
        """测试简单代码执行"""
        result = self.sandbox.run_code("print('Hello, world!')")
        self.assertTrue(result["success"])
        self.assertEqual(result["stdout"].strip(), "Hello, world!")
        self.assertEqual(result["stderr"], "")
    
    def test_code_with_error(self):
        """测试包含错误的代码"""
        result = self.sandbox.run_code("x = y + 1")  # NameError
        self.assertFalse(result["success"])
        self.assertIn("NameError", result["stderr"])
    
    def test_resource_limit(self):
        """测试资源限制"""
        # 创建一个内存密集型操作
        memory_code = """
large_list = [0] * 1000000000  # 尝试分配大量内存
print('This should not be printed due to memory limits')
"""
        result = self.sandbox.run_code(memory_code)
        # 在Docker中，超出内存限制通常会导致容器被杀死
        self.assertFalse(result["success"])
    
    def test_file_system_access(self):
        """测试文件系统访问限制"""
        # 尝试写入文件系统
        write_file_code = """
try:
    with open('/tmp/test.txt', 'w') as f:
        f.write('test')
    print('File written')
except Exception as e:
    print(f'Error: {e}')
"""
        result = self.sandbox.run_code(write_file_code)
        self.assertTrue(result["success"])  # 程序应该正常结束
        self.assertIn("Error", result["stdout"])  # 但应该报告错误
    
    def test_network_access(self):
        """测试网络访问限制"""
        network_code = """
import socket
try:
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.connect(('google.com', 80))
    print('Connected')
except Exception as e:
    print(f'Error: {e}')
"""
        result = self.sandbox.run_code(network_code)
        self.assertTrue(result["success"])  # 程序应该正常结束
        self.assertIn("Error", result["stdout"])  # 但应该报告连接错误
    
    def test_timeout(self):
        """测试超时功能"""
        timeout_sandbox = DockerSandbox(image_name="sandbox-test-image", timeout=2)
        result = timeout_sandbox.run_code("import time; time.sleep(10); print('Done')")
        self.assertFalse(result["success"])
        self.assertIn("timed out", result.get("error", ""))
    
    def test_environment_variables(self):
        """测试环境变量"""
        env_vars = {"TEST_VAR": "test_value"}
        result = self.sandbox.run_code("import os; print(os.environ.get('TEST_VAR', 'not set'))", env_vars)
        self.assertTrue(result["success"])
        self.assertEqual(result["stdout"].strip(), "test_value")
    
    @unittest.skip("需要安装Open Interpreter")
    def test_run_interpreter(self):
        """测试运行Open Interpreter（需要在容器中安装interpreter包）"""
        result = self.sandbox.run_interpreter("Hello, how are you?")
        self.assertTrue(result["success"])
        # 由于返回值依赖于interpreter的具体行为，这里只简单检查是否成功执行

if __name__ == "__main__":
    unittest.main() 