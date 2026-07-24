#!/usr/bin/env python3
"""
HAT-UA Weather Sensor — One-Launch Startup

Parameters are loaded from config/hat_ua_params.yaml by default.
Override on the command line:

  ros2 launch hat_ua hat_ua.launch.py                                   # YAML defaults
  ros2 launch hat_ua hat_ua.launch.py simulate:=true                    # no hardware
  ros2 launch hat_ua hat_ua.launch.py serial_dev:=/dev/hat_ua           # real sensor
  ros2 launch hat_ua hat_ua.launch.py leaf_id:=2 poll_rate:=2.0         # custom
"""

import os
from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, LogInfo
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def generate_launch_description():
    # Absolute path to the YAML config (works both source & install)
    pkg_share = get_package_share_directory('hat_ua')
    default_config = os.path.join(pkg_share, 'config', 'hat_ua_params.yaml')

    # -- User-exposed arguments (override YAML defaults) --
    serial_dev = LaunchConfiguration('serial_dev', default='/dev/hat_ua')
    leaf_id    = LaunchConfiguration('leaf_id',    default='1')
    baud_rate  = LaunchConfiguration('baud_rate',  default='9600')
    poll_rate  = LaunchConfiguration('poll_rate',  default='1.0')
    simulate   = LaunchConfiguration('simulate',   default='false')

    # -- Declare them so they show up in --show-arguments --
    args = [
        DeclareLaunchArgument('serial_dev', default_value='/dev/hat_ua',
            description='Serial port (use /dev/hat_ua after udev setup)'),
        DeclareLaunchArgument('leaf_id', default_value='1',
            description='Modbus slave ID (1~50)'),
        DeclareLaunchArgument('baud_rate', default_value='9600',
            description='Serial baud rate (HAT-UA fixed at 9600)'),
        DeclareLaunchArgument('poll_rate', default_value='1.0',
            description='Polling rate in Hz'),
        DeclareLaunchArgument('simulate', default_value='false',
            description='Simulation mode — no hardware needed'),
    ]

    # -- Nodes --
    driver = Node(
        package='hat_ua',
        executable='hat_ua_driver',
        name='hat_ua_driver',
        output='screen',
        parameters=[default_config, {
            # CLI overrides take precedence over YAML defaults
            'serial_dev_name': serial_dev,
            'modbus_leaf_id': leaf_id,
            'serial_baud_rate': baud_rate,
            'poll_rate': poll_rate,
            'simulate': simulate,
        }],
    )

    parser = Node(
        package='hat_ua',
        executable='hat_ua_parser',
        name='hat_ua_parser',
        output='screen',
    )

    return LaunchDescription(args + [
        driver,
        parser,
        LogInfo(msg=[
            'HAT-UA started — device: ', serial_dev,
            ', simulate: ', simulate, ', rate: ', poll_rate, ' Hz',
        ]),
    ])
