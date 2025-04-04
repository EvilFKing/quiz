from flask import Flask, render_template, jsonify
import docker
import psutil
import time
from sandbox import DockerSandbox

app = Flask(__name__)
docker_client = docker.from_env()

# 初始化沙箱实例
sandbox = DockerSandbox()

def get_container_info():
    """获取容器基本信息"""
    if not sandbox.container_id:
        return {
            'status': 'stopped',
            'id': '-',
            'uptime': '-'
        }
    
    try:
        container = docker_client.containers.get(sandbox.container_id)
        container_info = container.attrs
        
        # 获取容器状态
        status = container_info['State']['Status']
        if status == 'running':
            # 计算运行时间
            start_time = container_info['State']['StartedAt']
            if start_time:
                start_timestamp = time.strptime(start_time.split('.')[0], '%Y-%m-%dT%H:%M:%S')
                uptime_seconds = time.time() - time.mktime(start_timestamp)
                uptime = f"{int(uptime_seconds // 3600)}小时{int((uptime_seconds % 3600) // 60)}分钟"
            else:
                uptime = '-'
        else:
            uptime = '-'
            
        return {
            'status': status,
            'id': container.short_id,
            'uptime': uptime
        }
    except Exception as e:
        print(f"获取容器信息错误: {str(e)}")
        return {
            'status': 'error',
            'id': '-',
            'uptime': '-'
        }

def get_resource_usage():
    """获取资源使用情况"""
    if not sandbox.container_id:
        return {
            'cpu': 0,
            'memory': 0,
            'memoryUsed': '0MB',
            'memoryLimit': sandbox.memory_limit
        }
    
    try:
        container = docker_client.containers.get(sandbox.container_id)
        stats = container.stats(stream=False)
        
        # 计算CPU使用率
        cpu_delta = stats['cpu_stats']['cpu_usage']['total_usage'] - \
                    stats['precpu_stats']['cpu_usage']['total_usage']
        system_delta = stats['cpu_stats']['system_cpu_usage'] - \
                      stats['precpu_stats']['system_cpu_usage']
        num_cpus = len(stats['cpu_stats']['cpu_usage'].get('percpu_usage', [1]))
        cpu_usage = (cpu_delta / system_delta) * 100.0 * num_cpus
        
        # 计算内存使用率
        memory_usage = stats['memory_stats']['usage']
        memory_limit = stats['memory_stats']['limit']
        memory_percent = (memory_usage / memory_limit) * 100.0
        
        return {
            'cpu': round(cpu_usage, 1),
            'memory': round(memory_percent, 1),
            'memoryUsed': f"{memory_usage // (1024*1024)}MB",
            'memoryLimit': f"{memory_limit // (1024*1024)}MB"
        }
    except Exception as e:
        print(f"获取资源使用情况错误: {str(e)}")
        return {
            'cpu': 0,
            'memory': 0,
            'memoryUsed': '0MB',
            'memoryLimit': sandbox.memory_limit
        }

def get_security_config():
    """获取安全配置状态"""
    try:
        if not sandbox.container_id:
            return {
                'readOnly': False,
                'networkMode': 'bridge',
                'capsDropped': False
            }
            
        container = docker_client.containers.get(sandbox.container_id)
        container_info = container.attrs
        
        # 检查只读文件系统
        host_config = container_info.get('HostConfig', {})
        read_only = host_config.get('ReadonlyRootfs', False)
        
        # 检查网络模式
        network_mode = host_config.get('NetworkMode', 'bridge')
        
        # 检查能力限制
        cap_drop = host_config.get('CapDrop', [])
        
        return {
            'readOnly': read_only,
            'networkMode': network_mode,
            'capsDropped': len(cap_drop) > 0
        }
    except Exception as e:
        print(f"获取安全配置错误: {str(e)}")
        return {
            'readOnly': False,
            'networkMode': 'bridge',
            'capsDropped': False
        }

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/status')
def get_status():
    """获取Docker容器的完整状态信息"""
    try:
        return jsonify({
            'container': get_container_info(),
            'resources': get_resource_usage(),
            'security': get_security_config()
        })
    except Exception as e:
        return jsonify({
            'error': f'获取状态信息失败: {str(e)}'
        }), 500

if __name__ == '__main__':
    """启动监控"""
    app.run(host='0.0.0.0', port=5000, debug=True)