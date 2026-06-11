import sys
if sys.prefix == '/usr':
    sys.real_prefix = sys.prefix
    sys.prefix = sys.exec_prefix = '/home/kibeom/rescue_amr_project/bridge_ws/install/ares_bridges'
