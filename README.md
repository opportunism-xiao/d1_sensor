# HAT-UA Weather Sensor Driver for ROS2

基于 Modbus RTU 协议的 **HAT-UA 气象监测传感器** ROS2 驱动包。

**兼容 ROS2 Humble / Iron / Jazzy / Rolling。**

```
架构:  remote_serial → remote_modbus → remote_modbus_rtu → hat_ua
                                                              ├── hat_ua_driver (C++)   ← 轮询寄存器, 发布原始数据
                                                              └── hat_ua_parser (Python) ← 换算物理量, 发布 Float32 话题
```

---

## 硬件信息

| 项目 | 规格 |
|:---|:---|
| 传感器型号 | HAT-UA (广东大镓传感) |
| 通信协议 | Modbus RTU over USB (虚拟串口) |
| 默认从站地址 | 1 |
| 波特率 | 9600, 8N1 |
| USB 转串口芯片 | CH340 (ID: `1a86:7523`) 或 CP2102 (ID: `10c4:ea60`) |

### 寄存器地图 (官方参数表)

**测量值** (已解析，FC 0x03/0x04，只读):

| Addr (Hex) | Dec | 物理量 | 系数 | 单位 | 说明 |
|:---|:---|:---|:---|:---|:---|
| `0x0000` | 0 | 温度 | ×0.01 | ℃ | |
| `0x0001` | 1 | 湿度 | ×0.01 | %RH | |
| `0x0002` | 2 | 露点 | ×0.01 | ℃ | |
| `0x0003` | 3 | 气压 | ×0.1 | hPa | 1hPa = 1mBar |
| `0x0004` | 4 | 海拔 | ×0.2 | m | |
| `0x0005` | 5 | 空气密度 | ×0.001 | kg/m³ | |
| `0x0006` | 6 | **错误标志** | 1 | — | **非0 = 传感器故障，测量值不再更新** |

**历史记录 / 设置参数 / 校准系数** (未解析，可通过 `/modbus/hat_ua/raw` 获取原始值):

| Addr (Hex) | Dec | 内容 |
|:---|:---|:---|
| `0x0010`~`0x001B` | 16~27 | 历史最大/最小温度、湿度、露点、气压、海拔、空气密度 |
| `0x001C`~`0x001F` | 28~31 | 上电次数 (32位)、工作小时 (32位) |
| `0x0020` | 32 | 错误历史 |
| `0x0100` | 256 | 通信地址 (1~50，读写，FC 0x06) |
| `0x0102` | 258 | 用户命令 (100=重启, 101=重置标定, 102=重置ID=1) |
| `0x0104`~`0x0105` | 260~261 | 温度校准系数 K、B |

---

## ROS2 话题列表

| 话题 | 类型 | 说明 |
|:---|:---|:---|
| `/modbus/hat_ua/raw` | `hat_ua/msg/ModbusData` | 原始寄存器数组 |
| `/hat_ua/temperature` | `std_msgs/msg/Float32` | 温度 (℃) |
| `/hat_ua/humidity` | `std_msgs/msg/Float32` | 相对湿度 (%RH) |
| `/hat_ua/dew_point` | `std_msgs/msg/Float32` | 露点温度 (℃) |
| `/hat_ua/pressure` | `std_msgs/msg/Float32` | 大气压 (hPa) |
| `/hat_ua/altitude` | `std_msgs/msg/Float32` | 海拔 (m) |
| `/hat_ua/density` | `std_msgs/msg/Float32` | 空气密度 (kg/m³) |
| `/hat_ua/error_flag` | `std_msgs/msg/Float32` | 错误标志 (0=正常) |

---

## 第一步：环境准备

### 1.1 卸载 brltty (会占用串口设备)

```bash
sudo apt remove brltty -y
```

### 1.2 将当前用户加入 dialout 组 (获取串口权限)

```bash
sudo usermod -a -G dialout $USER
```

**必须注销后重新登录才能生效。** 重新登录后验证：

```bash
groups
# 输出中应该包含 dialout
```

### 1.3 确认串口设备

```bash
# 插上传感器，查看 USB 设备
lsusb | grep -i -E "ch340|cp210|serial|1a86"

# 查看串口设备权限
ls -l /dev/ttyUSB*
```

---

## 第二步：配置 udev 固定设备名 (防止 USB 插拔导致设备名变化)

### 2.1 查看传感器 USB VID/PID

```bash
# 方法1: lsusb 直接看
lsusb

# 方法2: 查看内核日志 (刚插上时)
sudo dmesg | grep -i "ttyUSB" | tail -5
# 示例输出: [xxx] usb 1-1: ch341-uart converter now attached to ttyUSB0
#           idVendor=1a86, idProduct=7523

# 方法3: 通过 sysfs 精确查看
udevadm info -a -n /dev/ttyUSB0 | grep -E "idVendor|idProduct|manufacturer|product" | head -10
```

### 2.2 创建 udev 规则文件

根据你的传感器 USB 芯片型号，选择对应规则。

**CH340 芯片** (VID=1a86, PID=7523，最常见):

```bash
sudo tee /etc/udev/rules.d/99-hat-ua.rules << 'EOF'
# HAT-UA Weather Sensor (CH340 USB-UART)
KERNEL=="ttyUSB*", ATTRS{idVendor}=="1a86", ATTRS{idProduct}=="7523", MODE:="0666", SYMLINK+="hat_ua"
EOF
```

**CP2102 芯片** (VID=10c4, PID=ea60):

```bash
sudo tee /etc/udev/rules.d/99-hat-ua.rules << 'EOF'
# HAT-UA Weather Sensor (CP2102 USB-UART)
KERNEL=="ttyUSB*", ATTRS{idVendor}=="10c4", ATTRS{idProduct}=="ea60", MODE:="0666", SYMLINK+="hat_ua"
EOF
```

> **注意**：如果你的传感器 VID/PID 与上面不同，请将 `idVendor` 和 `idProduct` 替换为 `udevadm info` 输出的实际值。

### 2.3 重载 udev 规则

```bash
sudo udevadm control --reload-rules
sudo udevadm trigger
```

### 2.4 验证

拔掉传感器，重新插入，然后检查：

```bash
ls -l /dev/hat_ua
# 输出: lrwxrwxrwx ... /dev/hat_ua -> ttyUSB0
```

之后启动驱动时，使用固定名称 `/dev/hat_ua` 即可，不再随 USB 端口变化。

---

## 第三步：编译

```bash
cd /home/gg/d1_sensor

# 安装 ROS2 依赖 (按你使用的发行版替换 $ROS_DISTRO)
# Humble / Iron / Jazzy / Rolling 等
sudo apt install -y \
  ros-$ROS_DISTRO-ament-cmake \
  ros-$ROS_DISTRO-rclcpp \
  ros-$ROS_DISTRO-std-msgs \
  ros-$ROS_DISTRO-rosidl-default-generators \
  ros-$ROS_DISTRO-yaml-cpp \
  python3-pip python3-setuptools

# 编译
colcon build --packages-up-to hat_ua
```

> **提示**：如果编译 Python 包时报 `--editable` 相关错误，将 setuptools 降到 < 65：
> ```bash
> pip install 'setuptools>=58.0,<65.0'
> ```

---

## 第四步：启动

### 方式 1：launch 文件 (推荐)

```bash
source install/setup.bash

# 使用 udev 固定名称
ros2 launch hat_ua hat_ua.launch.py serial_dev:=/dev/hat_ua

# 或直接用 ttyUSB0
ros2 launch hat_ua hat_ua.launch.py serial_dev:=/dev/ttyUSB0

# 完整参数
ros2 launch hat_ua hat_ua.launch.py \
  serial_dev:=/dev/hat_ua \
  leaf_id:=1 \
  baud_rate:=9600 \
  poll_rate:=1.0
```

### 方式 2：分别启动

```bash
# 终端1: 驱动节点
ros2 run hat_ua hat_ua_driver --ros-args \
  -p serial_dev_name:=/dev/hat_ua \
  -p serial_baud_rate:=9600 \
  -p modbus_leaf_id:=1

# 终端2: 解析节点
ros2 run hat_ua hat_ua_parser
```

### 启动参数说明

| 参数 | 类型 | 默认值 | 说明 |
|:---|:---|:---|:---|
| `serial_dev` | string | /dev/ttyUSB0 | 串口设备路径，推荐使用 `/dev/hat_ua` |
| `leaf_id` | int | 1 | Modbus 从站地址 |
| `baud_rate` | int | 9600 | 波特率 (HAT-UA 固定 9600) |
| `poll_rate` | double | 1.0 | 采样频率 (Hz) |

---

## 第五步：验证数据

```bash
source install/setup.bash

# 列出所有 hat_ua 话题
ros2 topic list | grep hat_ua

# 查看单个数值
ros2 topic echo /hat_ua/temperature

# 一次性查看所有物理量
ros2 topic echo /hat_ua/temperature &
ros2 topic echo /hat_ua/humidity &
ros2 topic echo /hat_ua/pressure &
ros2 topic echo /hat_ua/altitude &

# 查看原始寄存器数据 (调试用)
ros2 topic echo /modbus/hat_ua/raw

# 检查发布频率
ros2 topic hz /hat_ua/temperature

# 检查话题带宽
ros2 topic bw /hat_ua/temperature
```

正常输出示例：

```
data: 28.56
---
data: 45.20
---
data: 1013.20
---
```

---

## 参数修改速查

需要修改传感器适配参数时，涉及的文件：

| 修改内容 | 文件路径 | 位置 |
|:---|:---|:---|
| 寄存器地址/数量/系数 | [hat_ua/parser_node.py](src/hat_ua/hat_ua/parser_node.py) | `REGISTERS` 列表 |
| 轮询周期 | 启动参数 `poll_rate` | 无需改代码 |
| 从站地址 | 启动参数 `leaf_id` | 默认 1 |
| 串口波特率 | 启动参数 `baud_rate` | 默认 9600 |
| 话题名称前缀 | [parser_node.py:48](src/hat_ua/hat_ua/parser_node.py) | `topic = f'/hat_ua/{name}'` |
| 原始数据话题 | [driver_node.cpp:27](src/hat_ua/src/driver_node.cpp) | `"/modbus/hat_ua/raw"` 字符串 |
| Modbus 请求起始地址/数量 | [driver_node.cpp:94-95](src/hat_ua/src/driver_node.cpp) | `req->addr=0; req->count=7;` |
| 错误标志处理逻辑 | [parser_node.py:56](src/hat_ua/hat_ua/parser_node.py) | `if err != 0:` 分支 |
| int16 负数转换 | [parser_node.py:32](src/hat_ua/hat_ua/parser_node.py) | `_s16()` 函数 |

---

## 故障排查

| 现象 | 检查命令 | 常见原因 |
|:---|:---|:---|
| 找不到串口设备 | `ls /dev/ttyUSB* ; ls /dev/serial/by-id/` | 传感器未插入、USB 线故障 |
| Permission denied | `groups ; ls -l /dev/ttyUSB0` | 未加入 dialout 组 |
| 串口被占用 | `sudo lsof /dev/ttyUSB0` | brltty 或其他进程占用 |
| 无数据 / 异常码 | `ros2 topic echo /modbus/hat_ua/raw` | 波特率不对、从站地址错 |
| error_flag 非0 | 查看日志输出 | 传感器供电不足或接线松动 |
| 负数显示错误 | 对比 `ros2 topic echo /modbus/hat_ua/raw` 的 data 值 | int16 转换逻辑问题 |

---

## 许可证

Apache License 2.0
