from flask import Flask, render_template, jsonify
import docker
import psutil
import time

app = Flask(__name__, template_folder='.')
docker_client = docker.from_env()

def get_container_info():
    try:
        containers = docker_client.containers.list(all=True)
        if not containers:
            print("未找到任何容器")
            return []
            
        containers_info = []
        status_map = {
            'created': '已创建',
            'running': '运行中',
            'paused': '已暂停',
            'restarting': '重启中',
            'removing': '删除中',
            'exited': '已停止',
            'dead': '已死亡'
        }
        
        for container in containers:
            container_info = container.attrs
            state = container_info.get('State', {})
            status = state.get('Status', 'unknown')
            display_status = status_map.get(status, status)
            
            # 计算运行时间
            uptime = '-'
            if status == 'running':
                start_time = state.get('StartedAt')
                if start_time:
                    try:
                        start_timestamp = time.strptime(start_time.split('.')[0], '%Y-%m-%dT%H:%M:%S')
                        uptime_seconds = time.time() - time.mktime(start_timestamp)
                        hours = int(uptime_seconds // 3600)
                        minutes = int((uptime_seconds % 3600) // 60)
                        uptime = f"{hours}小时{minutes}分钟" if hours > 0 else f"{minutes}分钟"
                    except Exception as e:
                        print(f"计算运行时间错误: {str(e)}")
                        uptime = '-'
            
            containers_info.append({
                'name': container.name,
                'status': display_status,
                'id': container.short_id,
                'uptime': uptime
            })
            
        return containers_info
    except Exception as e:
        print(f"获取容器信息错误: {str(e)}")
        return []

def get_resource_usage():
    """获取资源使用情况"""
    print("开始获取资源使用情况...")
    containers = docker_client.containers.list()
    if not containers:
        print("未找到运行中的容器")
        return []
    
    containers_resources = []
    for container in containers:
        try:
            print(f"尝试获取容器统计信息，容器ID: {container.id}")
            stats = container.stats(stream=False)
            
            if not stats:
                print(f"警告：获取容器 {container.name} 统计信息失败")
                continue
            
            # 计算CPU使用率
            cpu_stats = stats.get('cpu_stats', {})
            precpu_stats = stats.get('precpu_stats', {})
            
            cpu_usage = 0
            try:
                cpu_delta = cpu_stats.get('cpu_usage', {}).get('total_usage', 0) - \
                           precpu_stats.get('cpu_usage', {}).get('total_usage', 0)
                system_delta = cpu_stats.get('system_cpu_usage', 0) - \
                              precpu_stats.get('system_cpu_usage', 0)
                if system_delta > 0:
                    num_cpus = len(cpu_stats.get('cpu_usage', {}).get('percpu_usage', [1]))
                    cpu_usage = (cpu_delta / system_delta) * 100.0 * num_cpus
            except Exception as e:
                print(f"计算CPU使用率错误: {str(e)}")
            
            # 计算内存使用率
            memory_stats = stats.get('memory_stats', {})
            memory_usage = memory_stats.get('usage', 0)
            memory_limit = memory_stats.get('limit', 0)
            
            memory_percent = 0
            if memory_limit > 0:
                memory_percent = (memory_usage / memory_limit) * 100.0
            
            containers_resources.append({
                'id': container.short_id,
                'name': container.name,
                'cpu': round(cpu_usage, 1),
                'memory': round(memory_percent, 1),
                'memoryUsed': f"{memory_usage // (1024*1024)}MB",
                'memoryLimit': f"{memory_limit // (1024*1024)}MB"
            })
        except Exception as e:
            print(f"获取容器 {container.name} 资源使用情况错误: {str(e)}")
            containers_resources.append({
                'id': container.short_id,
                'name': container.name,
                'cpu': 0,
                'memory': 0,
                'memoryUsed': '0MB',
                'memoryLimit': '0MB'
            })
    
    return containers_resources

def get_security_config():
    """获取安全配置状态"""
    print("开始获取安全配置信息...")
    try:
        containers = docker_client.containers.list()
        if not containers:
            print("未找到运行中的容器")
            return []
        
        containers_security = []
        for container in containers:
            try:
                print(f"尝试获取容器配置信息，容器ID: {container.id}")
                container_info = container.attrs
                
                if not container_info:
                    print(f"警告：获取容器 {container.name} 配置信息失败")
                    continue
                
                # 检查只读文件系统
                host_config = container_info.get('HostConfig', {})
                read_only = host_config.get('ReadonlyRootfs', False)
                
                # 检查网络模式
                network_mode = host_config.get('NetworkMode', 'bridge')
                
                # 检查能力限制
                cap_drop = host_config.get('CapDrop', [])
                
                containers_security.append({
                    'id': container.short_id,
                    'name': container.name,
                    'readOnly': read_only,
                    'networkMode': network_mode,
                    'capsDropped': len(cap_drop) > 0
                })
            except Exception as e:
                print(f"获取容器 {container.name} 安全配置错误: {str(e)}")
                containers_security.append({
                    'id': container.short_id,
                    'name': container.name,
                    'readOnly': False,
                    'networkMode': 'bridge',
                    'capsDropped': False
                })
        
        return containers_security
    except Exception as e:
        print(f"获取安全配置错误: {str(e)}")
        return []

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/status')
def get_status():
    """获取Docker容器的完整状态信息"""
    try:
        containers = get_container_info()
        resources = get_resource_usage()
        security = get_security_config()
        
        # 合并所有容器信息
        container_list = []
        for container in containers:
            container_data = container.copy()
            # 添加资源使用信息
            resource = next((r for r in resources if r['id'] == container['id']), None)
            if resource:
                container_data.update({
                    'cpu': resource['cpu'],
                    'memory': resource['memory'],
                    'memoryUsed': resource['memoryUsed'],
                    'memoryLimit': resource['memoryLimit']
                })
            
            # 添加安全配置信息
            security_config = next((s for s in security if s['id'] == container['id']), None)
            if security_config:
                container_data.update({
                    'readOnly': security_config['readOnly'],
                    'networkMode': security_config['networkMode'],
                    'capsDropped': security_config['capsDropped']
                })
            
            container_list.append(container_data)
        
        return jsonify({
            'containers': container_list
        })
    except Exception as e:
        return jsonify({
            'error': f'获取状态信息失败: {str(e)}'
        }), 500

if __name__ == '__main__':
    """启动监控"""
    app.run(host='0.0.0.0', port=5000, debug=True)