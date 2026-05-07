/* 

#include "rclcpp/rclcpp.hpp"
#include "geometry_msgs/msg/point.hpp"
#include "std_msgs/msg/float64_multi_array.hpp"

class VisualServoNode : public rclcpp::Node {
public:
    VisualServoNode() : Node("visual_servo_node"), kp_x(0.005), kp_y(0.005) {
        joint_pub = this->create_publisher<std_msgs::msg::Float64MultiArray>("joint_updates", 10);
        error_sub = this->create_subscription<geometry_msgs::msg::Point>(
            "pixel_error", 10, std::bind(&VisualServoNode::error_callback, this, std::placeholders::_1));
    }

private:
    void error_callback(const geometry_msgs::msg::Point::SharedPtr msg) const {
        auto joint_cmd = std_msgs::msg::Float64MultiArray();
        double pan_update = -msg->x * kp_x;
        double tilt_update = -msg->y * kp_y;
        
        joint_cmd.data = {pan_update, tilt_update};
        joint_pub->publish(joint_cmd);
    }

    rclcpp::Subscription<geometry_msgs::msg::Point>::SharedPtr error_sub;
    rclcpp::Publisher<std_msgs::msg::Float64MultiArray>::SharedPtr joint_pub;
    double kp_x;
    double kp_y;
};

int main(int argc, char * argv[]) {
    rclcpp::init(argc, argv);
    rclcpp::spin(std::make_shared<VisualServoNode>());
    rclcpp::shutdown();
    return 0;
}
    */