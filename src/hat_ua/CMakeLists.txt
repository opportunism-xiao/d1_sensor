cmake_minimum_required(VERSION 3.10)
project(hat_ua)

# ---- C++ standard ----
if(NOT CMAKE_CXX_STANDARD)
  set(CMAKE_CXX_STANDARD 20)
endif()
if(CMAKE_COMPILER_IS_GNUCXX OR CMAKE_CXX_COMPILER_ID MATCHES "Clang")
  add_compile_options(-Wall -Wextra -Wpedantic)
endif()

# ---- Dependencies ----
find_package(ament_cmake REQUIRED)
find_package(rosidl_default_generators REQUIRED)
find_package(rclcpp REQUIRED)
find_package(std_msgs REQUIRED)
find_package(remote_modbus REQUIRED)
find_package(remote_modbus_rtu REQUIRED)
find_package(remote_serial REQUIRED)

# ---- Detect Python version for install paths ----
find_package(Python3 REQUIRED COMPONENTS Interpreter)
execute_process(
  COMMAND ${Python3_EXECUTABLE} -c
    "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')"
  OUTPUT_VARIABLE _PYTHON_VER
  OUTPUT_STRIP_TRAILING_WHITESPACE)
message(STATUS "hat_ua: detected Python ${_PYTHON_VER}")

# ---- Message generation ----
rosidl_generate_interfaces(${PROJECT_NAME}
  "msg/ModbusData.msg"
  DEPENDENCIES std_msgs
)

# ---- C++ driver executable ----
add_executable(hat_ua_driver src/driver_node.cpp)
target_include_directories(hat_ua_driver PRIVATE
  ${rclcpp_INCLUDE_DIRS}
  ${remote_modbus_INCLUDE_DIRS}
  ${remote_modbus_rtu_INCLUDE_DIRS}
  ${remote_serial_INCLUDE_DIRS}
)
ament_target_dependencies(hat_ua_driver
  rclcpp std_msgs
  remote_modbus remote_modbus_rtu remote_serial
)
# Link the custom message typesupport
rosidl_get_typesupport_target(_cpp_typesupport ${PROJECT_NAME} "rosidl_typesupport_cpp")
target_link_libraries(hat_ua_driver ${_cpp_typesupport})

install(TARGETS hat_ua_driver
  DESTINATION lib/${PROJECT_NAME}
)

# ---- Python parser node ----
# Must install to the SAME prefix as rosidl (local/lib/pythonX.Y/dist-packages/)
# because Python only resolves ONE 'hat_ua' package — rosidl already places
# __init__.py and msg/*.py there.
install(DIRECTORY ${PROJECT_NAME}/
  DESTINATION local/lib/python${_PYTHON_VER}/dist-packages/${PROJECT_NAME}
)
install(PROGRAMS scripts/hat_ua_parser
  DESTINATION lib/${PROJECT_NAME}
)

# ---- Launch files ----
install(DIRECTORY launch
  DESTINATION share/${PROJECT_NAME}
)

ament_package()
