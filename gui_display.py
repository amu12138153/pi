"""
水质监测系统GUI界面
使用tkinter创建图形界面显示传感器数据
"""
import tkinter as tk
from tkinter import ttk, font
import threading
import time
from sensors import WaterQualitySensors

class WaterQualityGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("水质监测系统")
        self.root.geometry("600x500")
        self.root.configure(bg='#f0f0f0')
        
        # 初始化传感器
        try:
            self.sensors = WaterQualitySensors()
            self.sensor_ok = True
        except Exception as e:
            self.sensor_ok = False
            self.error_msg = str(e)
        
        # 创建界面
        self.create_widgets()
        
        # 启动数据更新线程
        if self.sensor_ok:
            self.update_data()
            self.start_update_thread()
    
    def create_widgets(self):
        """创建GUI组件"""
        # 标题
        title_font = font.Font(size=20, weight='bold')
        title_label = tk.Label(
            self.root, 
            text="水质监测系统", 
            font=title_font,
            bg='#f0f0f0',
            fg='#2c3e50'
        )
        title_label.pack(pady=20)
        
        if not self.sensor_ok:
            error_label = tk.Label(
                self.root,
                text=f"传感器初始化失败:\n{self.error_msg}",
                font=font.Font(size=12),
                bg='#f0f0f0',
                fg='red',
                justify='left'
            )
            error_label.pack(pady=20)
            return
        
        # 创建主框架
        main_frame = tk.Frame(self.root, bg='#f0f0f0')
        main_frame.pack(pady=10, padx=20, fill='both', expand=True)
        
        # 传感器数据显示框架
        data_font = font.Font(size=14)
        label_font = font.Font(size=12, weight='bold')
        
        # 水温
        temp_frame = self.create_sensor_frame(main_frame, "水温", "°C", label_font, data_font)
        temp_frame.pack(fill='x', pady=10)
        self.temp_label = temp_frame.winfo_children()[1]
        
        # pH值
        ph_frame = self.create_sensor_frame(main_frame, "pH值", "", label_font, data_font)
        ph_frame.pack(fill='x', pady=10)
        self.ph_label = ph_frame.winfo_children()[1]
        
        # 溶解氧
        do_frame = self.create_sensor_frame(main_frame, "溶解氧", "mg/L", label_font, data_font)
        do_frame.pack(fill='x', pady=10)
        self.do_label = do_frame.winfo_children()[1]
        
        # 浊度
        turb_frame = self.create_sensor_frame(main_frame, "浊度", "NTU", label_font, data_font)
        turb_frame.pack(fill='x', pady=10)
        self.turb_label = turb_frame.winfo_children()[1]
        
        # 状态标签
        self.status_label = tk.Label(
            main_frame,
            text="状态: 运行中",
            font=font.Font(size=10),
            bg='#f0f0f0',
            fg='green'
        )
        self.status_label.pack(pady=10)
        
        # 更新时间标签
        self.time_label = tk.Label(
            main_frame,
            text="",
            font=font.Font(size=9),
            bg='#f0f0f0',
            fg='gray'
        )
        self.time_label.pack()
    
    def create_sensor_frame(self, parent, name, unit, label_font, data_font):
        """创建传感器显示框架"""
        frame = tk.Frame(parent, bg='white', relief='raised', bd=2)
        
        # 传感器名称
        name_label = tk.Label(
            frame,
            text=f"{name}:",
            font=label_font,
            bg='white',
            anchor='w',
            width=12
        )
        name_label.pack(side='left', padx=15, pady=15)
        
        # 数据标签
        data_label = tk.Label(
            frame,
            text="--",
            font=data_font,
            bg='white',
            fg='#2c3e50',
            anchor='w'
        )
        data_label.pack(side='left', padx=10, pady=15)
        
        # 单位标签
        if unit:
            unit_label = tk.Label(
                frame,
                text=unit,
                font=font.Font(size=10),
                bg='white',
                fg='gray'
            )
            unit_label.pack(side='left', padx=5, pady=15)
        
        return frame
    
    def update_data(self):
        """更新传感器数据"""
        try:
            data = self.sensors.read_all()
            
            if data['status'] == 'OK':
                # 更新显示
                self.temp_label.config(text=f"{data['temperature']:.1f}")
                self.ph_label.config(text=f"{data['ph']:.2f}")
                self.do_label.config(text=f"{data['dissolved_oxygen']:.2f}")
                self.turb_label.config(text=f"{data['turbidity']:.2f}")
                self.status_label.config(text="状态: 正常", fg='green')
            else:
                self.status_label.config(text=f"状态: {data['status']}", fg='red')
            
            # 更新时间
            current_time = time.strftime("%Y-%m-%d %H:%M:%S")
            self.time_label.config(text=f"更新时间: {current_time}")
            
        except Exception as e:
            self.status_label.config(text=f"状态: 错误 - {str(e)}", fg='red')
    
    def start_update_thread(self):
        """启动数据更新线程"""
        def update_loop():
            while True:
                time.sleep(2)  # 每2秒更新一次
                self.root.after(0, self.update_data)
        
        thread = threading.Thread(target=update_loop, daemon=True)
        thread.start()
    
    def on_closing(self):
        """关闭程序时的清理"""
        if self.sensor_ok:
            self.sensors.close()
        self.root.destroy()

def main():
    """主函数"""
    root = tk.Tk()
    app = WaterQualityGUI(root)
    root.protocol("WM_DELETE_WINDOW", app.on_closing)
    root.mainloop()

if __name__ == "__main__":
    main()
