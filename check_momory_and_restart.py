"""
    监视指定容器的内存使用情况, 超过阈值自动重启
"""
import os
import time
import logging
from logging.handlers import TimedRotatingFileHandler


class ContainerMonitor:
    def __init__(self, log_file='container_check.log'):
        # 初始化时设置日志文件名并配置日志记录器
        self.log_file = log_file
        self.logger = self.setup_logger()

    def setup_logger(self):
        # 配置日志记录器，每天自动创建新文件，最多保留7天的日志
        logger = logging.getLogger()
        logger.setLevel(logging.INFO)
        handler = TimedRotatingFileHandler(self.log_file, when="midnight", interval=1, backupCount=7)
        handler.setFormatter(logging.Formatter('%(asctime)s - %(message)s', datefmt='%Y-%m-%d %H:%M:%S'))
        logger.addHandler(handler)
        return logger

    def execute_command(self, cmd):
        # 执行系统命令并捕获可能出现的异常
        try:
            return os.popen(cmd).read().strip()
        except Exception as e:
            self.logger.error(f"执行命令 {cmd} 时出错: {e}")
            return None

    def convert_memory_usage(self, usage_str):
        # 将内存使用情况从字符串转换为以GiB为单位的数值
        units = {"GiB": 1, "MiB": 1/1024, "KiB": 1/(1024**2)}
        for unit in units:
            if unit in usage_str:
                try:
                    return float(usage_str.replace(unit, "").strip()) * units[unit]
                except ValueError:
                    break
        return None

    def get_container_mem_usage(self, container_name):
        # 获取指定容器的内存使用情况
        cmd = f"docker stats {container_name} --no-stream --format '{{{{.MemUsage}}}}'"
        result = self.execute_command(cmd)
        
        if result is None:
            self.logger.error(f"获取 {container_name} 的内存使用情况时出错.")
            return None

        usage, _ = result.split(" / ")
        mem_usage = self.convert_memory_usage(usage)
        if mem_usage is None:
            self.logger.error(f"无法解析 {container_name} 的内存使用数据: {result}")
        return mem_usage

    def is_container_running(self, container_name):
        # 检查指定的容器是否在运行
        cmd = f"docker ps --filter 'name={container_name}'"
        result = self.execute_command(cmd)
        return container_name in result if result is not None else False

    def restart_container(self, container_name):
        # 重启指定的容器，并捕获可能出现的异常
        try:
            os.system(f"docker restart {container_name}")
            self.logger.info(f"已于 {time.strftime('%Y-%m-%d %H:%M:%S')} 重启 {container_name}")
        except Exception as e:
            self.logger.error(f"重启 {container_name} 时出错: {e}")

    def monitor(self, containers, sleep_time=300):
        # 主监控循环，定期检查容器的内存使用情况，并根据需要重启容器
        while True:
            self.logger.info("\n开始检查容器内存使用情况...")
            for container_name, threshold in containers.items():
                mem_usage = self.get_container_mem_usage(container_name)
                is_running = self.is_container_running(container_name)

                if mem_usage is not None:
                    self.logger.info(f"{container_name} 的内存使用情况: {mem_usage:.2f}GiB")
                
                if not is_running or (mem_usage is not None and mem_usage > threshold):
                    self.logger.warning(f"正在重启 {container_name}...")
                    self.restart_container(container_name)
                elif mem_usage is None:
                    self.logger.warning(f"{container_name} 没有启动或获取数据失败.")

            time.sleep(sleep_time)


if __name__ == "__main__":
    # 定义需要监控的容器及其内存使用阈值，并开始监控
    containers = {
        "gaoxinzhihuishuili-dev": 24,
        "yiyuan_service-dev": 24,
        "uav_hehusiluan": 7,
        "binzou_wurenji": 16
    }
    sleep_time = 600
    monitor = ContainerMonitor()
    monitor.monitor(containers, sleep_time)