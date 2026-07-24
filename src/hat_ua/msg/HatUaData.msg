# HAT-UA 完整气象数据 (所有物理量合并为单条消息)
std_msgs/Header header          # 时间戳
float32 temperature             # 温度 (℃)
float32 humidity                # 湿度 (%RH)
float32 dew_point               # 露点 (℃)
float32 pressure                # 气压 (hPa)
float32 altitude                # 海拔 (m)
float32 density                 # 空气密度 (kg/m³)
int16 error_flag                # 错误标志 (0=正常)
