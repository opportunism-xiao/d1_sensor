# HAT-UA 气象传感器 ROS2 驱动

基于 Modbus RTU over USB 驱动 **HAT-UA 气象监测传感器**（广东大镓传感），
发布温度、湿度、露点、气压、海拔、空气密度 6 项物理量。

**兼容 ROS2 Humble / Iron / Jazzy / Rolling。**

```
架构:  remote_serial → remote_modbus → remote_modbus_rtu → hat_ua
                          ├── hat_ua_driver (C++)    轮询 0x0000~0x0006，发布 /modbus/hat_ua/raw
                          └── hat_ua_parser (Python)  换算物理量，发布 /hat_ua/* 话题
```

---

## 硬件信息

| 项目 | 规格 |
|:---|:---|
| 传感器 | HAT-UA (广东大镓传感) |
| 通信 | Modbus RTU over USB，9600-8N1 |
| 从站地址 | 1 (出厂默认，可通过 0x0100 寄存器修改) |
| USB 芯片 | CP210x 系列 (ID: `10c4:ea60`)，备选 CH340 (ID: `1a86:7523`) |

### 寄存器地图 (官方参数表)

**测量值** (已解析，FC 0x03/0x04，int16，只读):

| Addr | Dec | 物理量 | 系数 | 单位 | 备注 |
|:---|:---|:---|:---|:---|:---|
| `0x0000` | 0 | 温度 | ×0.01 | ℃ | |
| `0x0001` | 1 | 湿度 | ×0.01 | %RH | |
| `0x0002` | 2 | 露点 | ×0.01 | ℃ | |
| `0x0003` | 3 | 气压 | ×0.1 | hPa | 1hPa = 1mBar |
| `0x0004` | 4 | 海拔 | ×0.2 | m | |
| `0x0005` | 5 | 空气密度 | ×0.001 | kg/m³ | |
| `0x0006` | 6 | 错误标志 | 1 | — | **非0=传感器故障，数据不再发布** |

参考：历史记录 (`0x0010`~`0x0020`)、设置参数 (`0x0100`~`0x0102`)、校准系数 (`0x0104`~`0x0105`)。

---

## ROS2 话题

| 话题 | 类型 | 说明 |
|:---|:---|:---|
| `/hat_ua/all` | `hat_ua/msg/HatUaData` | **合并话题 — 一条消息包含全部 7 个字段** |
| `/hat_ua/temperature` | `std_msgs/msg/Float32` | 温度 (℃) |
| `/hat_ua/humidity` | `std_msgs/msg/Float32` | 湿度 (%RH) |
| `/hat_ua/dew_point` | `std_msgs/msg/Float32` | 露点 (℃) |
| `/hat_ua/pressure` | `std_msgs/msg/Float32` | 气压 (hPa) |
| `/hat_ua/altitude` | `std_msgs/msg/Float32` | 海拔 (m) |
| `/hat_ua/density` | `std_msgs/msg/Float32` | 空气密度 (kg/m³) |
| `/hat_ua/error_flag` | `std_msgs/msg/Float32` | 错误标志 (0=正常) |
| `/modbus/hat_ua/raw` | `hat_ua/msg/ModbusData` | 原始寄存器数组 (调试用) |

---

## 第一步：环境准备

### 1.1 卸载 brltty

```bash
sudo apt remove brltty -y
```

### 1.2 串口权限

```bash
sudo usermod -a -G dialout $USER
# 注销重新登录后生效，验证:
groups   # 应包含 dialout
```

### 1.3 确认串口

```bash
lsusb | grep -i -E "cp210|ch340|1a86"
ls -l /dev/ttyUSB*
```

---

## 第二步：udev 固定设备名

### 2.1 查 VID/PID

```bash
sudo dmesg | grep -i "ttyUSB" | tail -5
# CP210x: cp210x converter now attached to ttyUSB0  idVendor=10c4, idProduct=ea60
# CH340:  ch341-uart converter now attached to ttyUSB0  idVendor=1a86, idProduct=7523
```

### 2.2 创建规则

**CP210x (最常见):**

```bash
sudo tee /etc/udev/rules.d/99-hat-ua.rules << 'EOF'
KERNEL=="ttyUSB*", ATTRS{idVendor}=="10c4", ATTRS{idProduct}=="ea60", MODE:="0666", SYMLINK+="hat_ua"
EOF
```

**CH340:**

```bash
sudo tee /etc/udev/rules.d/99-hat-ua.rules << 'EOF'
KERNEL=="ttyUSB*", ATTRS{idVendor}=="1a86", ATTRS{idProduct}=="7523", MODE:="0666", SYMLINK+="hat_ua"
EOF
```

### 2.3 生效

```bash
sudo udevadm control --reload-rules
sudo udevadm trigger
# 拔插传感器后验证:
ls -l /dev/hat_ua   # → ttyUSB0
```

---

## 第三步：编译

```bash
cd /home/gg/d1_sensor

sudo apt install -y \
  ros-$ROS_DISTRO-ament-cmake \
  ros-$ROS_DISTRO-rclcpp \
  ros-$ROS_DISTRO-std-msgs \
  ros-$ROS_DISTRO-rosidl-default-generators \
  ros-$ROS_DISTRO-yaml-cpp \
  python3-pip

colcon build --packages-up-to hat_ua
```

> 如果 Python 包报 `--editable` 错误：`pip install 'setuptools>=58.0,<65.0'`

---

## 第四步：启动

```bash
source install/setup.bash

# 仿真模式 — 无传感器也能跑
ros2 launch hat_ua hat_ua.launch.py simulate:=true

# 真实传感器
ros2 launch hat_ua hat_ua.launch.py serial_dev:=/dev/hat_ua

# 完整参数
ros2 launch hat_ua hat_ua.launch.py \
  serial_dev:=/dev/hat_ua \
  leaf_id:=1 \
  baud_rate:=9600 \
  poll_rate:=1.0 \
  simulate:=false
```

| 参数 | 默认值 | 说明 |
|:---|:---|:---|
| `serial_dev` | `/dev/ttyUSB0` | 串口路径，推荐 `/dev/hat_ua` |
| `leaf_id` | `1` | Modbus 从站地址 |
| `baud_rate` | `9600` | 波特率 |
| `poll_rate` | `1.0` | 采样频率 (Hz) |
| `simulate` | `false` | 仿真模式 (`true` = 无需硬件) |

---

## 第五步：验证

```bash
source install/setup.bash

# 一条消息拿全部数据
ros2 topic echo /hat_ua/all

# 只看温度
ros2 topic echo /hat_ua/temperature

# 检查发布频率
ros2 topic hz /hat_ua/all

# 原始寄存器 (调试)
ros2 topic echo /modbus/hat_ua/raw
```

`/hat_ua/all` 输出示例：

```
header:
  stamp: ...
temperature: 25.70
humidity: 50.09
dew_point: 13.58
pressure: 1008.40
altitude: 49.80
density: 1.183
error_flag: 0
```

---

## 参数修改速查

| 修改内容 | 文件 | 位置 |
|:---|:---|:---|
| 寄存器系数/单位 | [parser_node.py](src/hat_ua/hat_ua/parser_node.py) | `REGISTERS` 列表 |
| 从站地址 | 启动参数 `leaf_id` | 默认 1 |
| 波特率 | 启动参数 `baud_rate` | 默认 9600 |
| 采样频率 | 启动参数 `poll_rate` | 默认 1.0 |
| 话题前缀 `/hat_ua/` | [parser_node.py](src/hat_ua/hat_ua/parser_node.py) | `topic = f'/hat_ua/{name}'` |
| 原始数据话题 | [driver_node.cpp](src/hat_ua/src/driver_node.cpp) | `"/modbus/hat_ua/raw"` |
| 读取起始地址/数量 | [driver_node.cpp](src/hat_ua/src/driver_node.cpp) | `req->addr, req->count` |
| 错误标志行为 | [parser_node.py](src/hat_ua/hat_ua/parser_node.py) | `if err != 0: return` |
| int16 转换 | [parser_node.py](src/hat_ua/hat_ua/parser_node.py) | `_s16()` |

---

## 故障排查

| 现象 | 检查 | 原因 |
|:---|:---|:---|
| 找不到串口 | `ls /dev/ttyUSB*` | 传感器未插入 |
| Permission denied | `groups` | 未加入 dialout 组 |
| 串口被占用 | `sudo lsof /dev/ttyUSB0` | brltty 未卸载 |
| 无数据 | `ros2 topic echo /modbus/hat_ua/raw` | 波特率/从站地址不对 |
| error_flag 非0 | 日志 | 传感器故障或强 EMI 干扰 |
| 先试仿真 | `ros2 launch hat_ua hat_ua.launch.py simulate:=true` | 确认软件链路正常 |

## 许可证

Apache License 2.0
