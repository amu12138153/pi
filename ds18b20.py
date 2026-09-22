"""
DS18B20温度传感器读取模块
DS18B20接在GPIO13，使用1-Wire协议
"""
import os
import glob
import time

class DS18B20:
    def __init__(self, gpio_pin=4):
        """
        初始化DS18B20
        :param gpio_pin: GPIO引脚号（默认13）
        """
        self.gpio_pin = gpio_pin
        self.base_dir = '/sys/bus/w1/devices/'
        self.device_folder = None
        self.device_file = None
        self._find_device()
    
    def _find_device(self):
        """查找DS18B20设备"""
        # 确保1-Wire模块已加载
        os.system('modprobe w1-gpio')
        os.system('modprobe w1-therm')
        
        # 查找28开头的设备（DS18B20的设备ID以28开头）
        device_folders = glob.glob(self.base_dir + '28*')
        
        if len(device_folders) == 0:
            raise RuntimeError(f"未找到DS18B20设备，请检查GPIO{self.gpio_pin}连接")
        
        self.device_folder = device_folders[0]
        self.device_file = self.device_folder + '/w1_slave'
    
    def _read_temp_raw(self):
        """读取原始温度数据"""
        try:
            with open(self.device_file, 'r') as f:
                lines = f.readlines()
            return lines
        except Exception as e:
            raise RuntimeError(f"读取DS18B20失败: {e}")
    
    def get_temp(self):
        """
        获取温度值
        :return: 温度值（摄氏度，精度0.1度，例如25.5返回255）
        """
        lines = self._read_temp_raw()
        
        # 检查CRC校验
        while lines[0].strip()[-3:] != 'YES':
            time.sleep(0.2)
            lines = self._read_temp_raw()
        
        # 提取温度值
        equals_pos = lines[1].find('t=')
        if equals_pos != -1:
            temp_string = lines[1][equals_pos + 2:]
            temp_c = float(temp_string) / 1000.0  # 转换为摄氏度
            # 返回与C代码兼容的格式（整数，精度0.1度）
            return int(temp_c * 10)
        else:
            raise RuntimeError("无法从DS18B20读取温度值")
    
    def get_temp_float(self):
        """
        获取温度值（浮点数）
        :return: 温度值（摄氏度）
        """
        temp_int = self.get_temp()
        return temp_int / 10.0
