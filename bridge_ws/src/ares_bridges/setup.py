import os
from glob import glob
from setuptools import find_packages, setup

package_name = "ares_bridges"

setup(
    name=package_name,
    version="0.0.0",
    packages=find_packages(exclude=["test"]),
    data_files=[
        ("share/ament_index/resource_index/packages", ["resource/" + package_name]),
        ("share/" + package_name, ["package.xml"]),
        # 💡 런치 파일이 빌드 시 포함되도록 추가
        (
            os.path.join("share", package_name, "launch"),
            glob(os.path.join("launch", "*launch.[pxy][yma]*")),
        ),
    ],
    install_requires=["setuptools"],
    zip_safe=True,
    maintainer="kibeom",
    maintainer_email="devkibeom@gmail.com",
    description="ARES Project: Standalone Communication Bridges",
    license="TODO: License declaration",
    tests_require=["pytest"],
    entry_points={
        "console_scripts": [
            # 💡 3개의 브릿지 노드를 터미널 명령어(executable)로 등록
            "webrtc_bridge = ares_bridges.webrtc_bridge:main",
            "robot_status_bridge = ares_bridges.robot_status_bridge:main",
            "ai_vision_bridge = ares_bridges.ai_vision_bridge:main",
        ],
    },
)
