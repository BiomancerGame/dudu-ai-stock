"""pytest 公共夹具。"""
from __future__ import annotations

import os
import sys

# 让 tests 可以直接导入项目根目录的模块
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
