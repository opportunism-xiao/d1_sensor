#!/usr/bin/env python3
"""
HAT-UA Weather Sensor — Parser Node

Subscribes to /modbus/hat_ua/raw (ModbusData), converts raw register values
to physical quantities, and publishes them in two forms:
  - /hat_ua/all — HatUaData (single message with all 7 fields)
  - /hat_ua/temperature ... /hat_ua/error_flag — Float32 (one per field)

=======================================================================
  HAT-UA Register Map (official, FC 0x03 / 0x04, int16, read-only)
=======================================================================
  Addr(Hex)  Dec    Name             Scale    Unit    Notes
  ───────────────────────────────────────────────────────────────────
  0x0000       0   温度              0.01     ℃
  0x0001       1   湿度              0.01     %RH
  0x0002       2   露点              0.01     ℃
  0x0003       3   气压              0.1      hPa     1hPa = 1mBar
  0x0004       4   海拔              0.2      m
  0x0005       5   空气密度          0.001    kg/m³
  0x0006       6   错误标志          1        —       非0 = 传感器故障
  ───────────────────────────────────────────────────────────────────
  (Historical records at 0x0010~0x0020 not parsed by this node)
  (Configuration / calibration at 0x0100~0x0105 not implemented)
=======================================================================
"""

import rclpy
from rclpy.node import Node
from std_msgs.msg import Float32
from hat_ua.msg import ModbusData, HatUaData


def _s16(raw: int) -> int:
    """uint16 → int16: 0xFFFF = -1, 0x8000 = -32768"""
    return raw - 65536 if raw > 32767 else raw


# (data[] index, topic_suffix, scale, unit)
REGISTERS = [
    (0, 'temperature', 0.01,  '℃'),        # 0x0000  温度
    (1, 'humidity',    0.01,  '%RH'),       # 0x0001  湿度
    (2, 'dew_point',   0.01,  '℃'),        # 0x0002  露点
    (3, 'pressure',    0.1,   'hPa'),       # 0x0003  气压  1hPa=100Pa=0.1KPa=1mBar
    (4, 'altitude',    0.2,   'm'),         # 0x0004  海拔
    (5, 'density',     0.001, 'kg/m³'),     # 0x0005  空气密度
    (6, 'error_flag',  1.0,   ''),          # 0x0006  错误标志
]


class HatUaParser(Node):
    """Parse raw ModbusData → physical Float32 topics."""

    def __init__(self):
        super().__init__('hat_ua_parser')

        self.pubs = {}
        for idx, name, scale, unit in REGISTERS:
            topic = f'/hat_ua/{name}'
            self.pubs[name] = self.create_publisher(Float32, topic, 10)
            self.get_logger().info(f'  {name:12s} → {topic}  ({unit})')

        # 合并话题 — 一条消息包含全部物理量
        self.all_pub = self.create_publisher(HatUaData, '/hat_ua/all', 10)

        self.sub = self.create_subscription(
            ModbusData, '/modbus/hat_ua/raw', self._cb, 10)

        self.get_logger().info('  all         → /hat_ua/all  (combined)')
        self.get_logger().info('HAT-UA Parser ready, waiting for data...')

    def _cb(self, msg: ModbusData):
        if len(msg.data) < 7:
            self.get_logger().warning(
                f'Short message: got {len(msg.data)} regs, expected 7',
                throttle_duration_sec=5.0)
            return

        err = _s16(msg.data[6])

        # Per HAT-UA spec: error_flag != 0 means sensor fault.
        # Measurements are FROZEN — do NOT publish stale data.
        # Errors may be caused by internal failure or strong EMI nearby;
        # when EMI disappears the flag returns to 0 and data resumes.
        if err != 0:
            self.get_logger().error(
                f'SENSOR FAULT (error_flag={err}): '
                'internal error or strong EMI — data NOT published. '
                'Inspect sensor. Values will resume when flag clears.',
                throttle_duration_sec=5.0)
            return

        vals = {}
        for idx, name, scale, _unit in REGISTERS:
            phys = _s16(msg.data[idx]) * scale
            f32 = Float32(data=phys)
            self.pubs[name].publish(f32)
            vals[name] = phys

        # 合并消息
        all_msg = HatUaData()
        all_msg.header = msg.header
        all_msg.temperature = vals['temperature']
        all_msg.humidity    = vals['humidity']
        all_msg.dew_point   = vals['dew_point']
        all_msg.pressure    = vals['pressure']
        all_msg.altitude    = vals['altitude']
        all_msg.density     = vals['density']
        all_msg.error_flag  = int(vals['error_flag'])
        self.all_pub.publish(all_msg)

        self.get_logger().info(
            f'T={vals["temperature"]:.1f}℃  '
            f'H={vals["humidity"]:.1f}%  '
            f'Td={vals["dew_point"]:.1f}℃  '
            f'P={vals["pressure"]:.1f}hPa  '
            f'Alt={vals["altitude"]:.1f}m  '
            f'ρ={vals["density"]:.3f}kg/m³  '
            f'Err=0',
            throttle_duration_sec=10.0)


def main(args=None):
    rclpy.init(args=args)
    node = HatUaParser()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
