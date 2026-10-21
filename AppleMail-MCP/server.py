import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SRC = ROOT / "src"

if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))


if __name__ == "__main__":
    from apple_mcp_common.bundle import drop_unexpanded_user_config

    drop_unexpanded_user_config()
    from apple_mail_mcp.tools import main

    main()
