from pathlib import Path
import sys

ROOT_DIR = Path(__file__).resolve().parent
SRC_DIR = ROOT_DIR / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))


def main() -> None:
    from apple_files_mcp.tools import mcp

    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
