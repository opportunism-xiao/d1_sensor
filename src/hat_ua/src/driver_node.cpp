/*
 * HAT-UA Weather Sensor Driver
 * Modbus RTU polling node — reads registers 0x0000~0x0006, publishes raw data.
 *
 * Supports a simulate mode for testing without hardware.
 */

#include <chrono>
#include <cmath>
#include <memory>
#include <random>
#include <string>
#include <thread>
#include <atomic>

#include "rclcpp/rclcpp.hpp"
#include "hat_ua/msg/modbus_data.hpp"
#include "remote_modbus/interface.hpp"
#include "remote_modbus_rtu/factory.hpp"
#include "remote_modbus/srv/holding_register_read.hpp"

class HatUaDriver : public rclcpp::Node {
 public:
  HatUaDriver() : rclcpp::Node("hat_ua_driver"), running_(true) {
    // ---- parameters ----
    this->declare_parameter("poll_rate", 1.0);
    this->declare_parameter("simulate", false);

    double poll_rate = this->get_parameter("poll_rate").as_double();
    if (poll_rate <= 0.0) {
      RCLCPP_WARN(this->get_logger(),
                  "poll_rate=%.2f is invalid, clamping to 0.1 Hz", poll_rate);
      poll_rate = 0.1;
    }
    poll_interval_ms_ = static_cast<int>(1000.0 / poll_rate);

    simulate_ = this->get_parameter("simulate").as_bool();

    RCLCPP_INFO(this->get_logger(),
                "HAT-UA Driver starting: poll_rate=%.1f Hz  simulate=%s",
                poll_rate, simulate_ ? "true" : "false");

    // ---- publisher ----
    raw_pub_ = this->create_publisher<hat_ua::msg::ModbusData>(
        "/modbus/hat_ua/raw", 10);

    clock_ = this->get_clock();

    // ---- init ----
    if (simulate_) {
      RCLCPP_INFO(this->get_logger(),
                  "Simulation mode — no hardware required");
    } else {
      try {
        modbus_ = remote_modbus_rtu::Factory::New(this);
        RCLCPP_INFO(this->get_logger(), "Modbus RTU interface ready");
      } catch (const std::exception &e) {
        RCLCPP_FATAL(this->get_logger(),
                     "Modbus RTU init failed: %s. "
                     "Retry with `simulate:=true` for testing without sensor.",
                     e.what());
        throw;
      }
    }

    // ---- start polling ----
    poll_thread_ = std::thread(&HatUaDriver::poll_loop, this);
  }

  ~HatUaDriver() {
    running_ = false;
    if (poll_thread_.joinable()) poll_thread_.join();
    RCLCPP_INFO(this->get_logger(), "HAT-UA Driver stopped");
  }

 private:
  // ---- real hardware poll ----
  void poll_real() {
    auto req =
        std::make_shared<remote_modbus::srv::HoldingRegisterRead::Request>();
    req->leaf_id = 1;
    req->addr    = 0x0000;   // 起始地址 (温度)
    req->count   = 7;        // 连续读 0x0000 ~ 0x0006

    auto resp =
        std::make_shared<remote_modbus::srv::HoldingRegisterRead::Response>();
    modbus_->holding_register_read(req, resp);   // blocking (~60ms timeout)

    if (!running_) return;

    hat_ua::msg::ModbusData msg;
    msg.header.stamp    = clock_->now();
    msg.header.frame_id = "hat_ua_raw";
    msg.leaf_id         = req->leaf_id;
    msg.data.reserve(7);

    if (resp->exception_code != 0) {
      RCLCPP_WARN(this->get_logger(),
                  "Modbus exception: leaf=%d code=%d",
                  req->leaf_id, resp->exception_code);
    } else if (resp->values.size() >= 7) {
      for (size_t i = 0; i < 7; i++)
        msg.data.push_back(static_cast<int16_t>(resp->values[i]));
      RCLCPP_DEBUG(this->get_logger(),
                   "Data: [T=%d H=%d D=%d P=%d A=%d ρ=%d E=%d]",
                   msg.data[0], msg.data[1], msg.data[2],
                   msg.data[3], msg.data[4], msg.data[5], msg.data[6]);
    } else {
      RCLCPP_ERROR(this->get_logger(),
                   "Short response: %zu regs, expected 7", resp->values.size());
    }

    raw_pub_->publish(msg);
  }

  // ---- simulation poll: realistic fake data ----
  void poll_simulate() {
    hat_ua::msg::ModbusData msg;
    msg.header.stamp    = clock_->now();
    msg.header.frame_id = "hat_ua_sim";
    msg.leaf_id         = 1;
    msg.data.reserve(7);

    // 温度:    ~25°C   → 2500  (±80)
    // 湿度:    ~50%    → 5000  (±200)
    // 露点:    ~14°C   → 1400  (±50)
    // 气压:    ~1013hPa → 10130 (±50)
    // 海拔:    ~50m    → 250   (±10)
    // 密度:    ~1.18   → 1180  (±5)
    // 错误标志: 0

    auto jitter = [this]() -> int16_t {
      std::uniform_int_distribution<int16_t> d(range_);
      return static_cast<int16_t>(d(rng_));
    };

    static int16_t base[] = {2500, 5000, 1400, 10130, 250, 1180, 0};
    static int16_t jit[]  = {80,   200,  50,   50,    10,  5,    0};

    for (size_t i = 0; i < 7; i++) {
      if (i == 6) {
        // error_flag always 0 in simulation
        msg.data.push_back(0);
      } else {
        int16_t noise = static_cast<int16_t>(std::sin(counter_ * 0.05 + i) * jit[i]);
        int16_t val   = base[i] + noise + jitter();
        msg.data.push_back(val);
      }
    }
    counter_++;

    raw_pub_->publish(msg);

    RCLCPP_DEBUG(this->get_logger(),
                 "Sim: [T=%d H=%d D=%d P=%d A=%d ρ=%d E=%d]",
                 msg.data[0], msg.data[1], msg.data[2],
                 msg.data[3], msg.data[4], msg.data[5], msg.data[6]);
  }

  // ---- main loop ----
  void poll_loop() {
    RCLCPP_INFO(this->get_logger(), "Polling thread started (%s)",
                simulate_ ? "simulate" : "real");

    while (running_ && rclcpp::ok()) {
      auto start = std::chrono::steady_clock::now();

      if (simulate_) {
        poll_simulate();
      } else {
        poll_real();
      }

      if (!running_) break;

      auto elapsed = std::chrono::steady_clock::now() - start;
      auto remain  = std::chrono::milliseconds(poll_interval_ms_) - elapsed;
      if (remain > std::chrono::milliseconds(0))
        std::this_thread::sleep_for(remain);
    }
  }

  // ---- members ----
  bool simulate_{false};
  std::shared_ptr<remote_modbus::Interface> modbus_;
  rclcpp::Publisher<hat_ua::msg::ModbusData>::SharedPtr raw_pub_;
  rclcpp::Clock::SharedPtr clock_;

  std::thread poll_thread_;
  std::atomic<bool> running_{true};
  int poll_interval_ms_{1000};

  // simulation state
  std::mt19937 rng_{std::random_device{}()};
  std::uniform_int_distribution<int16_t> range_{-2, 2};
  int counter_{0};
};

int main(int argc, char **argv) {
  rclcpp::init(argc, argv);
  auto node = std::make_shared<HatUaDriver>();
  rclcpp::executors::SingleThreadedExecutor exec;
  exec.add_node(node);
  exec.spin();
  rclcpp::shutdown();
  return 0;
}
