from launch import LaunchDescription
from launch_ros.actions import Node
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration

def generate_launch_description():
    # 실행 시 로봇 ID를 동적으로 받을 수 있도록 설정 (기본값: robot5)
    robot_id = LaunchConfiguration('robot_id', default='robot5')

    return LaunchDescription([
        DeclareLaunchArgument(
            'robot_id',
            default_value='robot5',
            description='ID of the robot to bridge'
        ),
        
        # 1. WebRTC 영상/데이터 스트리밍 브릿지
        Node(
            package='ares_bridges',
            executable='webrtc_bridge',
            name='webrtc_bridge',
            output='screen',
            parameters=[{
                'port': 8002,
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
