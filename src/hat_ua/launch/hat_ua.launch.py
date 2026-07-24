#!/usr/bin/env python3
"""
HAT-UA Weather Sensor — One-Launch Startup

Starts driver (C++) + parser (Python) together.

Usage:
  ros2 launch hat_ua hat_ua.launch.py                         # auto-detect
  ros2 launch hat_ua hat_ua.launch.py simulate:=true           # test without hardware
  ros2 launch hat_ua hat_ua.launch.py serial_dev:=/dev/hat_ua  # real sensor
"""

import glob
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, LogInfo
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def generate_launch_description():
    # ---- auto-detect USB device ----
    default_dev = '/dev/ttyUSB0'
    candidates = glob.glob('/dev/serial/by-id/usb*')
    if candidates:
        default_dev = candidates[0]

    # ---- arguments ----
    serial_dev_arg = DeclareLaunchArgument(
        'serial_dev', default_value=default_dev,
        description='Serial port. Use /dev/serial/by-id/... for stability.')

    leaf_id_arg = DeclareLaunchArgument(
        'leaf_id', default_value='1',
        description='Modbus slave ID (HAT-UA default: 1)')

    poll_rate_arg = DeclareLaunchArgument(
        'poll_rate', default_value='1.0',
        description='Polling rate in Hz')

    baud_arg = DeclareLaunchArgument(
        'baud_rate', default_value='9600',
        description='Serial baud rate (HAT-UA: 9600)')

    simulate_arg = DeclareLaunchArgument(
        'simulate', default_value='false',
        description='Run with fake data (no hardware needed)')

    # ---- driver node (C++) ----
    driver = Node(
        package='hat_ua',
        executable='hat_ua_driver',
        name='hat_ua_driver',
        output='screen',
        parameters=[{
            'modbus_is_remote': False,
            'modbus_prefix': '/modbus/hat_ua',
            'modbus_leaf_id': LaunchConfiguration('leaf_id'),
            'serial_is_remote': False,
            'serial_prefix': '/serial/hat_ua',
            'serial_dev_name': LaunchConfiguration('serial_dev'),
            'serial_baud_rate': LaunchConfiguration('baud_rate'),
            'serial_data': 8,
            'serial_parity': False,
            'serial_stop': 1,
            'serial_flow_control': False,
            'poll_rate': LaunchConfiguration('poll_rate'),
            'simulate': LaunchConfiguration('simulate'),
        }],
    )

    # ---- parser node (Python) ----
    parser = Node(
        package='hat_ua',
        executable='hat_ua_parser',
        name='hat_ua_parser',
        output='screen',
    )

    return LaunchDescription([
        serial_dev_arg,
        leaf_id_arg,
        poll_rate_arg,
        baud_arg,
        simulate_arg,
        driver,
        parser,
        LogInfo(msg=['HAT-UA starting — simulate: ', LaunchConfiguration('simulate'),
                     ', device: ', LaunchConfiguration('serial_dev')]),
    ])
