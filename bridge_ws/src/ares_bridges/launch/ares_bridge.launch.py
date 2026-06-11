from launch import LaunchDescription
from launch_ros.actions import Node
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration
from launch_ros.parameter_descriptions import ParameterValue

def generate_launch_description():
    # 실행 시 로봇 ID와 포트를 동적으로 받음 (로봇별 1포트 — 견고한 분리 구조)
    #   robot5(TB_05): ros2 launch ares_bridges ares_bridge.launch.py robot_id:=robot5 port:=8002
    #   두 번째 로봇 : ros2 launch ares_bridges ares_bridge.launch.py robot_id:=robot1 port:=8003
    robot_id = LaunchConfiguration('robot_id', default='robot5')
    port = LaunchConfiguration('port', default='8002')

    return LaunchDescription([
        DeclareLaunchArgument(
            'robot_id',
            default_value='robot5',
            description='ID of the robot to bridge (e.g. robot1, robot5)'
        ),
        DeclareLaunchArgument(
            'port',
            default_value='8002',
            description='WebRTC 브릿지 /offer 포트 (로봇별 고유 — 프론트 idx0=8002, idx1=8003)'
        ),

        # 1. WebRTC 영상/데이터 스트리밍 브릿지
        Node(
            package='ares_bridges',
            executable='webrtc_bridge',
            name='webrtc_bridge',
            output='screen',
            parameters=[{
                'port': ParameterValue(port, value_type=int),
                'topic': ['/', robot_id, '/survivor/annotated'], # 압축 토픽이 복구되면 /compressed 추가
                'robot': robot_id
            }]
        ),

        # 2. 로봇 상태(배터리, 위치) 백엔드 동기화 브릿지
        Node(
            package='ares_bridges',
            executable='robot_status_bridge',
            name='robot_status_bridge',
            output='screen',
            parameters=[{
                'robot_id': robot_id
            }]
        ),

        # 3. AI 얼굴 크롭 이미지 백엔드 매칭 브릿지
        Node(
            package='ares_bridges',
            executable='ai_vision_bridge',
            name='ai_vision_bridge',
            output='screen',
            parameters=[{
                'robot_id': robot_id
            }]
        ),
    ])
