"""PyInstaller 打包用入口。放在项目根目录，使用绝对导入。"""
import sys
from pathlib import Path

# 确保项目根目录在 sys.path 里（PyInstaller 打包后会自动处理，但开发时需要）
_ROOT = Path(__file__).resolve().parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from mkr.app import main  # noqa: E402

if __name__ == "__main__":
    main()
