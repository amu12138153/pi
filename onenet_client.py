import json
import time
import paho.mqtt.client as mqtt


class OneNetClient:
    def __init__(self):
        # OneNET 基本配置
        self.product_id = "7ojdV4UE4x"
        self.device_name = "test1"
        self.token = "version=2018-10-31&res=products%2F7ojdV4UE4x%2Fdevices%2Ftest1&et=1922948897&method=md5&sign=R%2Fjpgr9uM1fRBed2yPcJ5A%3D%3D"

        self.broker = "mqtts.heclouds.com"
        self.port = 1883

        # Topic 定义
        self.topic_post = f"$sys/{self.product_id}/{self.device_name}/thing/property/post"
        self.topic_post_reply = f"$sys/{self.product_id}/{self.device_name}/thing/property/post/reply"
        self.topic_set = f"$sys/{self.product_id}/{self.device_name}/thing/property/set"
        self.topic_set_reply = f"$sys/{self.product_id}/{self.device_name}/thing/property/set_reply"

        # 本地状态缓存
        self.cloud_ctrl = {
            'heater': False,
            'pump': False,
            'buzzer': False,
            'led': False,
            'feeder': False
        }

        self.client = mqtt.Client(client_id=self.device_name, protocol=mqtt.MQTTv311)
        self.client.username_pw_set(username=self.product_id, password=self.token)

        self.client.on_connect = self.on_connect
        self.client.on_message = self.on_message

        self.connected = False

    def on_connect(self, client, userdata, flags, rc):
        if rc == 0:
            print("[OneNET] 连接成功！")
            self.connected = True
            client.subscribe(self.topic_post_reply)
            client.subscribe(self.topic_set)
        else:
            print(f"[OneNET] 连接失败，错误码: {rc}")
            self.connected = False

    def on_message(self, client, userdata, msg):
        try:
            payload = json.loads(msg.payload.decode('utf-8'))

            if msg.topic == self.topic_post_reply:
                code = payload.get('code')
                if code == 200:
                    pass
                else:
                    print(f"[OneNET反馈] 上报失败! 码: {code}, 消息: {payload.get('msg')}")

            elif msg.topic == self.topic_set:
                print(f"[OneNET指令] 收到控制命令: {payload}")
                self.handle_control_command(payload)

        except Exception as e:
            print(f"[OneNET] 消息解析错误: {e}")

    def handle_control_command(self, payload):
        cmd_id = payload.get('id')
        params = payload.get('params', {})

        for key in self.cloud_ctrl.keys():
            if key in params:
                self.cloud_ctrl[key] = params[key]
                print(f"   >>> 更新云端指令: {key} -> {self.cloud_ctrl[key]}")

        reply_msg = {"id": cmd_id, "code": 200, "msg": "success"}
        self.client.publish(self.topic_set_reply, json.dumps(reply_msg))

    def get_cloud_command(self):
        return self.cloud_ctrl

    def start(self):
        try:
            self.client.connect(self.broker, self.port, 60)
            self.client.loop_start()
        except Exception as e:
            print(f"[OneNET] 连接异常: {e}")

    def upload_data(self, sensor_data, device_states=None):
        """
        上报传感器数据 + 设备状态
        修正：将 Boolean 强制转换为 bool 类型 (生成 json true/false)，绝不能用 int
        """
        if not self.connected: return
        if sensor_data.get('status') != 'OK': return

        try:
            # 1. 传感器数据
            params = {
                "temperature": {"value": round(float(sensor_data.get('temperature', 0)), 1)},
                "ph": {"value": round(float(sensor_data.get('ph', 0)), 2)},
                "dissolved_oxygen": {"value": round(float(sensor_data.get('dissolved_oxygen', 0)), 2)},
                "turbidity": {"value": round(float(sensor_data.get('turbidity', 0)), 2)}
            }

            # 2. 设备状态 (关键修改：使用 bool() 确保是 true/false)
            if device_states:
                params["heater"] = {"value": bool(device_states.get('heater', False))}
                params["pump"] = {"value": bool(device_states.get('pump', False))}
                params["feeder"] = {"value": bool(device_states.get('feeder', False))}
                params["buzzer"] = {"value": bool(device_states.get('buzzer', False))}
                params["led"] = {"value": bool(device_states.get('led', False))}

            payload = {
                "id": str(int(time.time())),
                "version": "1.0",
                "params": params
            }

            self.client.publish(self.topic_post, json.dumps(payload))
            # 打印日志方便调试
            if device_states:
                # 打印出来是 True/False，但发送出去的 json 会自动变成 true/false
                print(f"[OneNET] 状态已同步: Buzzer={params['buzzer']['value']}, LED={params['led']['value']}")

        except Exception as e:
            print(f"[OneNET] 上报构造异常: {e}")

    def stop(self):
        self.client.loop_stop()
        self.client.disconnect()