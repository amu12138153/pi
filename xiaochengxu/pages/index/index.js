Page({
  data: {
    // OneNET 配置
    pid: '7ojdV4UE4x',
    device_name: 'test1',
    // 你的产品级 Token
    api_token: 'version=2018-10-31&res=products%2F7ojdV4UE4x%2Fdevices%2Ftest1&et=1922948897&method=md5&sign=R%2Fjpgr9uM1fRBed2yPcJ5A%3D%3D', 

    // 设备状态 (必须初始化)
    device: {
      heater: false,
      pump: false,
      buzzer: false,
      led: false,
      feeder: false
    },
    
    // 传感器数据
    sensor: {},

    // 【核心变量】记录最后一次手指点击的时间
    lastOperateTime: 0 
  },

  onLoad: function () {
    this.fetchData(); 
    // 每 3 秒刷新一次数据
    this.timer = setInterval(() => {
      this.fetchData();
    }, 3000);
  },

  onUnload: function () {
    if (this.timer) clearInterval(this.timer);
  },

  // --- 核心功能 1: 霸道的开关控制 (解决回弹) ---
  onSwitchChange: function (e) {
    const id = e.currentTarget.dataset.id; // 获取是哪个设备 (led/heater...)
    const value = e.detail.value;          // 获取目标状态 (true/false)
    
    console.log(`[手动操作] ${id} -> ${value}`);

    // 【防回弹第一招】记录当前时间，开启 4秒 "云端屏蔽罩"
    // 在这 4秒内，fetchData 函数会自动闭嘴，不更新开关状态
    this.setData({ lastOperateTime: Date.now() });

    // 【防回弹第二招】乐观更新 (Optimistic Update)
    // 不等服务器回复，直接修改界面显示！让用户觉得零延迟
    // 这样开关就会稳稳地停在你点的位置，绝对不会弹回去
    let updateLocal = {};
    updateLocal[`device.${id}`] = value;
    this.setData(updateLocal);

    // 发送指令给 OneNET
    wx.request({
      url: 'https://iot-api.heclouds.com/thingmodel/set-device-property',
      method: 'POST',
      header: {
        'Authorization': this.data.api_token,
        'Content-Type': 'application/json'
      },
      data: {
        "product_id": this.data.pid,
        "device_name": this.data.device_name,
        "params": { [id]: value }
      },
      success: (res) => {
        if (res.data.code === 0) {
          wx.showToast({ title: '指令已下发', icon: 'none' });
        } else {
          // 如果真的发送失败了，再把开关拨回去，告诉用户不行
          console.error("控制失败", res);
          updateLocal[`device.${id}`] = !value;
          this.setData(updateLocal);
          wx.showToast({ title: '控制失败', icon: 'none' });
        }
      },
      fail: () => {
        // 网络断了，也要拨回去
        updateLocal[`device.${id}`] = !value;
        this.setData(updateLocal);
        wx.showToast({ title: '网络异常', icon: 'none' });
      }
    });
  },

  // --- 核心功能 2: 智能的数据同步 (解决不同步) ---
  fetchData: function () {
    const that = this;
    const url = `https://iot-api.heclouds.com/thingmodel/query-device-property?product_id=${this.data.pid}&device_name=${this.data.device_name}`;

    wx.request({
      url: url,
      method: 'GET',
      header: { 'Authorization': this.data.api_token },
      success(res) {
        if (res.data.code === 0 && res.data.data) {
          const props = res.data.data;
          
          let newDevice = { ...that.data.device }; // 复制当前状态
          let newSensor = { ...that.data.sensor };

          // 检查现在是不是 "保护期"
          // 如果离最后一次点击不到 4000ms，说明用户刚动过手
          // 这时候我们只更新传感器，坚决不碰开关，防止回弹！
          const isUserOperating = (Date.now() - that.data.lastOperateTime) < 4000;

          props.forEach(item => {
            const key = item.identifier; // 比如 "led", "temperature"
            const val = item.value;      // 云端的值
            
            // 1. 传感器数据：随便更新，不需要保护
            if (['temperature', 'ph', 'dissolved_oxygen', 'turbidity'].includes(key)) {
               newSensor[key] = val;
            }

            // 2. 设备开关：只有在 "非保护期" 才同步
            if (!isUserOperating) {
              if (['heater', 'pump', 'buzzer', 'led', 'feeder'].includes(key)) {
                // 【兼容性处理】OneNET有时返回 1, 有时返回 "1", 有时返回 true
                // 我们统一把它们转换成布尔值，确保 switch 能识别
                newDevice[key] = (val == 1 || val == '1' || val == true || val == 'true');
              }
            }
          });

          // 更新数据
          that.setData({
            sensor: newSensor,
            // 如果在保护期，就保留本地的 device (不更新)，否则用云端的 device
            device: isUserOperating ? that.data.device : newDevice
          });
          
          if (isUserOperating) {
            console.log("用户操作中... 暂停同步开关状态");
          }
        }
      }
    });
  }
});