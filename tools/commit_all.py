# tools/commit_all.py
import sys, os, shutil, json
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from utils.commitment import build_commitments_for_round, DEFAULT_SCALE, DEFAULT_CHUNK


def main():
    # Usage: python3 tools/commit_all.py /path/to/zkp_root /path/to/commits_root [--skip-if-exists]
    if len(sys.argv) < 3:
        print("Usage: python3 tools/commit_all.py /path/to/zkp_root /path/to/commits_root [--skip-if-exists]")
        sys.exit(1)

    zkp_root = sys.argv[1]
    commits_root = sys.argv[2]
    skip_flag = ["--skip-if-exists"] if (len(sys.argv) > 3 and sys.argv[3] == "--skip-if-exists") else []

    rounds = sorted([d for d in glob.glob(os.path.join(zkp_root, "round*")) if os.path.isdir(d)])
    print("Rounds détectés :", ", ".join(os.path.basename(r) for r in rounds))

    for rd in rounds:
        name = os.path.basename(rd)
        print(f"\n==> Commit {rd}  ->  {os.path.join(commits_root, name)}")
        subprocess.check_call([sys.executable, os.path.join(os.path.dirname(__file__), "commit_round.py"), rd, commits_root, *skip_flag])

if __name__ == "__main__":
    main()
