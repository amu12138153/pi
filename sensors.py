"""
水质传感器读取模块 (RS485 独立容错架构版)
包含：溶解氧(地址1)、pH(地址2)、浊度(地址3)、水温(DS18B20)
说明：任意传感器缺失或损坏，不会影响其他传感器的读取。
"""
import time
import minimalmodbus
import serial
from ds18b20 import DS18B20

class WaterQualitySensors:
    def __init__(self):
        """初始化所有传感器"""
        self.temp_sensor = DS18B20(gpio_pin=4)
        self.rs485_ok = False

        try:
            # 挂载设备，即使物理上没接，这里初始化对象也不会报错
            self.do_sensor = minimalmodbus.Instrument('/dev/ttyUSB0', 1)
            self.ph_sensor = minimalmodbus.Instrument('/dev/ttyUSB0', 2)
            self.turb_sensor = minimalmodbus.Instrument('/dev/ttyUSB0', 3)

            # 统一配置总线物理参数
            self.do_sensor.serial.baudrate = 4800
            self.do_sensor.serial.bytesize = 8
            self.do_sensor.serial.parity   = serial.PARITY_NONE
            self.do_sensor.serial.stopbits = 1
            self.do_sensor.serial.timeout  = 1.0

            # 设置通信模式并清除脏数据
            for sensor in [self.do_sensor, self.ph_sensor, self.turb_sensor]:
                sensor.mode = minimalmodbus.MODE_RTU
                sensor.clear_buffers_before_each_transaction = True

            self.rs485_ok = True
            print("✅ RS485 总线初始化成功！(支持设备热插拔/缺失容错)")
        except Exception as e:
            print(f"❌ RS485 初始化失败，请检查 USB 模块: {e}")

    def get_temperature_float(self):
        return self.temp_sensor.get_temp_float()

    def read_ph(self):
        if not self.rs485_ok: return None
        try:
            raw_val = self.ph_sensor.read_register(0, functioncode=3, signed=False)
            return raw_val / 100.0
        except Exception:
            return None  # 读取失败时返回 None，而不是让程序崩溃

    def read_dissolved_oxygen(self):
        if not self.rs485_ok: return None
        try:
            return self.do_sensor.read_float(2, functioncode=3, number_of_registers=2)
        except Exception:
            return None

    def read_turbidity(self):
        if not self.rs485_ok: return None
        try:
            raw_val = self.turb_sensor.read_register(0, functioncode=3, signed=False)
            return raw_val / 100.0
        except Exception:
            # 你目前没接浊度，这里会静默触发，返回 None 给主程序
            return None

    def read_all(self):
        """一键打包所有数据供主程序调用"""
        if not self.rs485_ok:
            return {
                'temperature': None, 'ph': None, 'dissolved_oxygen': None,
                'turbidity': None, 'status': 'Error: RS485未连接'
            }

        # 依次独立读取，加入 50ms 硬件切换延时防冲撞
        temperature = self.get_temperature_float()

        do_value = self.read_dissolved_oxygen()
        time.sleep(0.05)

        ph = self.read_ph()
        time.sleep(0.05)

        turbidity = self.read_turbidity()
        time.sleep(0.05)

        # 检查是否全部宕机
        if do_value is None and ph is None and turbidity is None:
            status = 'Error: 所有 RS485 传感器均无响应'
        else:
            status = 'OK'

        return {
            'temperature': temperature,
            'ph': ph,
            'dissolved_oxygen': do_value,
            'turbidity': turbidity,
            'status': status
        }

    def close(self):
        if self.rs485_ok:
            self.do_sensor.serial.close()