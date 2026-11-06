"""Create a ZIP from staged Git files only, after the staged privacy audit passes."""
from pathlib import Path
import argparse
import subprocess
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[1]
DESTINATION = ROOT.parent / f"{ROOT.name}.zip"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output", type=Path,
        help="write the audited archive here (relative paths resolve beside the project folder)",
    )
    args = parser.parse_args()
    destination = args.output or DESTINATION
    if not destination.is_absolute():
        destination = ROOT.parent / destination
    destination = destination.resolve()
    audit = subprocess.run([sys.executable, str(ROOT / "scripts" / "privacy_audit.py")], cwd=ROOT)
    if audit.returncode:
        return audit.returncode
    if destination.exists():
        print(f"Refusing to overwrite existing archive: {destination}")
        return 2
    listing = subprocess.run(
        ["git", "-C", str(ROOT), "ls-files", "--cached", "-z"],
        check=True, capture_output=True,
    )
    files = [Path(name.decode("utf-8")) for name in listing.stdout.split(b"\0") if name]
    if not files:
        print("No staged files found.")
        return 2
    with zipfile.ZipFile(destination, "x", compression=zipfile.ZIP_DEFLATED, compresslevel=7) as archive:
        for relative in files:
            archive.write(ROOT / relative, Path(ROOT.name) / relative)
    print(f"Created {destination.name} from {len(files)} audited staged files.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
