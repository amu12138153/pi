"""
水质监测系统主程序 (实时控制 + 长周期高精度记录 双轨分离版)
功能：
1. 实时轨：每 3 秒极速读取、控制硬件、同步 OneNET
2. 记录轨：每 20 分钟高精度采样 50 次滤波，保存至内存
3. 存储轨：每 24 小时将内存数据落地为 CSV
"""
import time
import sys
import os
import csv
from datetime import datetime
from sensors import WaterQualitySensors
from gpiozero import Buzzer, LED, OutputDevice
from onenet_client import OneNetClient

# === 阈值设置 ===
TEMP_MIN = 20.0
TEMP_MAX = 35.0
PH_MIN = 6.5
PH_MAX = 8.5
DO_MIN = 4.0
DO_MAX = 14.0
TURB_MAX = 1000.0

# 全局变量：用于在内存中暂存 24 小时内的高精度数据
daily_csv_records = []


def collect_aggregated_data(sensors):
    """
    延时记录任务核心引擎 (16次中值平均滤波版):
    单次记录 16 组数据，剔除 3 个极大值和 3 个极小值，剩下的 10 组求平均作为最终特征。
    """
    print(f"\n[{time.strftime('%H:%M:%S')}] ---> 开始执行 20 分钟周期高精度采样 (共 16 组) <---")
    records = []

    # 1. 精确采集 16 组数据
    for i in range(16):
        data = sensors.read_all()
        if data['status'] == 'OK':
            records.append(data)

        # 打印覆盖式进度条，不刷屏
        sys.stdout.write(f"\r正在采集第 {i + 1}/16 组数据...")
        sys.stdout.flush()
        time.sleep(1.0)  # 每次采集间隔 1 秒

    print("\n采样完毕，正在进行极值剔除与平均计算...\n")

    # 容错：如果总线故障导致连 7 组成功的数据都没读到，直接抛错丢弃本次记录
    if len(records) <= 6:
        return {'status': 'Error: 总线干扰或设备无响应，有效数据不足以进行滤波计算'}

    # 2. 提取各项物理量数值列表
    temps = [d['temperature'] for d in records if d['temperature'] is not None]
    phs = [d['ph'] for d in records if d['ph'] is not None]
    dos = [d['dissolved_oxygen'] for d in records if d['dissolved_oxygen'] is not None]
    turbs = [d['turbidity'] for d in records if d['turbidity'] is not None]

    # 3. 核心滤波算法：排序 -> 去 3 大去 3 小 -> 求均值
    def filter_and_avg(lst):
        if not lst: return 0.0
        # 只要成功采集的样本大于 6 个，就执行掐头去尾
        if len(lst) > 6:
            lst.sort()
            lst = lst[3:-3]  # 完美剔除前 3 个极小值和后 3 个极大值

        # 此时如果满载，剩下的正好是中间最平稳的 10 个数据
        return sum(lst) / len(lst)

    # 4. 组装最终喂给预测模型的高质量数据
    avg_data = {
        'temperature': filter_and_avg(temps),
        'ph': filter_and_avg(phs),
        'dissolved_oxygen': filter_and_avg(dos),
        'turbidity': filter_and_avg(turbs),
        'status': 'OK',
    }
    return avg_data

def save_daily_csv():
    """存储任务：将内存中的 24 小时数据写入 CSV 文件"""
    global daily_csv_records
    if not daily_csv_records:
        return

    date_str = datetime.now().strftime("%Y-%m-%d_%H-%M")
    filename = f"water_log_{date_str}.csv"

    try:
        with open(filename, mode='w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(['测量时间', '水温(°C)', 'pH值', '溶解氧(mg/L)', '浊度(NTU)'])

            for r in daily_csv_records:
                writer.writerow([
                    r['time'],
                    f"{r['temperature']:.2f}",
                    f"{r['ph']:.2f}",
                    f"{r['dissolved_oxygen']:.2f}",
                    f"{r['turbidity']:.2f}"
                ])

        print(f"\n[{time.strftime('%H:%M:%S')}] >>> 成功将 6 小时数据 ({len(daily_csv_records)}条) 保存至文件: {filename} <<<")
        daily_csv_records.clear()
    except Exception as e:
        print(f"\n[{time.strftime('%H:%M:%S')}] 保存CSV失败: {e}")

def apply_controls(data, devices, cloud_cmds):
    """实时控制任务：硬件设备自动化与云端融合控制"""
    buzzer = devices["buzzer"]
    led = devices["led"]
    heater = devices["heater"]
    pump = devices["pump"]
    feeder = devices["feeder"]

    auto_heater = False
    auto_pump = False
    auto_alarm = False

    temp = data.get('temperature')
    ph = data.get('ph')
    do = data.get('dissolved_oxygen')
    turb = data.get('turbidity')
    status = data.get('status')

    if temp is not None:
        if temp < TEMP_MIN: auto_heater = True
        elif heater.is_active and temp < TEMP_MIN + 0.5: auto_heater = True
        if temp < TEMP_MIN or temp > TEMP_MAX: auto_alarm = True
    else: auto_alarm = True

    if turb is not None:
        if turb > TURB_MAX:
            auto_pump = True
            auto_alarm = True
    else: auto_alarm = True

    if ph is None or ph < PH_MIN or ph > PH_MAX: auto_alarm = True
    if do is None or do < DO_MIN or do > DO_MAX: auto_alarm = True
    if status != 'OK': auto_alarm = True

    final_heater = auto_heater or cloud_cmds.get('heater', False)
    final_pump = auto_pump or cloud_cmds.get('pump', False)
    final_buzzer = auto_alarm or cloud_cmds.get('buzzer', False)
    final_led = auto_alarm or cloud_cmds.get('led', False)
    final_feeder = cloud_cmds.get('feeder', False)

    if final_heater: heater.on()
    else: heater.off()

    if final_pump: pump.on()
    else: pump.off()

    if final_feeder: feeder.on()
    else: feeder.off()

    if final_buzzer: buzzer.on()
    else: buzzer.off()

    if final_led: led.on()
    else: led.off()

    return {"heater": final_heater, "pump": final_pump, "feeder": final_feeder, "buzzer": final_buzzer, "led": final_led}

def print_data(data, device_states, cloud_cmds, record_count):
    """打印监控面板"""
    print("\n" + "=" * 50)
    print(f"OneNET云端指令: {cloud_cmds}")
    print(f"本地内存已缓存的高精度记录数: {record_count}")
    print("-" * 50)

    if data['status'] == 'OK':
        # 安全格式化：如果有数据就保留小数，如果没有就显示"未接入"
        temp_str = f"{data['temperature']:.1f}°C" if data['temperature'] is not None else "未接入"
        ph_str = f"{data['ph']:.2f}" if data['ph'] is not None else "未接入"
        do_str = f"{data['dissolved_oxygen']:.2f} mg/L" if data['dissolved_oxygen'] is not None else "未接入"
        turb_str = f"{data['turbidity']:.1f} NTU" if data['turbidity'] is not None else "未接入"

        print(f"水温: {temp_str:<12} |  pH值: {ph_str}")
        print(f"溶氧: {do_str:<12} |  浊度: {turb_str}")
    else:
        print(f"传感器错误: {data['status']}")

    print("-" * 50)
    print(f"加热棒: {'开启' if device_states['heater'] else '关闭'}   水泵: {'开启' if device_states['pump'] else '关闭'}")
    print("=" * 50)
def main():
    print("系统启动，进入 [实时控制 + 延时记录] 双轨模式...")
    try:
        devices = {"buzzer": Buzzer(17), "led": LED(16), "heater": OutputDevice(13), "pump": OutputDevice(12), "feeder": OutputDevice(18)}
    except Exception as e:
        print(f"GPIO初始化失败: {e}"); sys.exit(1)

    try:
        onenet = OneNetClient(); onenet.start()
    except Exception as e:
        print(f"OneNET连接失败: {e}"); sys.exit(1)

    try:
        sensors = WaterQualitySensors()
    except Exception as e:
        print(f"传感器错误: {e}"); sys.exit(1)

    last_realtime_time = 0
    last_record_time = time.time()
    last_csv_save_time = time.time()

    try:
        while True:
            current_time = time.time()

            # === [存储轨] 每 24 小时保存 CSV ===
            if current_time - last_csv_save_time >= 6 * 60 * 60:
                save_daily_csv()
                last_csv_save_time = time.time()

            # === [记录轨] 每 20 分钟进行高精度采样 ===
            if current_time - last_record_time >= 20 * 60:
                record_data = collect_aggregated_data(sensors)
                if record_data['status'] == 'OK':
                    daily_csv_records.append({
                        'time': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                        'temperature': record_data['temperature'],
                        'ph': record_data['ph'],
                        'dissolved_oxygen': record_data['dissolved_oxygen'],
                        'turbidity': record_data['turbidity']
                    })
                last_record_time = time.time()
                # 采样耗时较长，重置一下当前时间，防止立刻触发实时任务累积
                current_time = time.time()

            # === [实时轨] 每 3 秒进行极速读取、控制与云同步 ===
            if current_time - last_realtime_time >= 3:
                # 1. 极速读取一次传感器数据
                rt_data = sensors.read_all()

                # 2. 获取云端干预指令
                cloud_cmds = onenet.get_cloud_command()

                # 3. 立即执行硬件控制 (如果超标，继电器会立刻动作)
                current_states = apply_controls(rt_data, devices, cloud_cmds)

                # 4. 刷新终端显示
                print_data(rt_data, current_states, cloud_cmds, len(daily_csv_records))

                # 5. 秒级上传至 OneNET 小程序
                onenet.upload_data(rt_data, current_states)

                last_realtime_time = time.time()

            # 主循环极短休眠，降低 CPU 负载且保证响应敏捷
            time.sleep(0.1)

    except KeyboardInterrupt:
        print("\n收到停止信号，正在保存尚未落地的内存数据...")
        save_daily_csv()
    finally:
        onenet.stop()
        sensors.close()
        for dev in devices.values():
            try: dev.off(); dev.close()
            except: pass

if __name__ == "__main__":
    main()