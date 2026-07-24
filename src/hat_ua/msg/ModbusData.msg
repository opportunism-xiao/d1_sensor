# ModbusData.msg - 原始 Modbus 寄存器数据
std_msgs/Header header      # 时间戳和帧信息
uint8 leaf_id               # 从站地址
int16[] data                # 寄存器原始值数组（int16）
