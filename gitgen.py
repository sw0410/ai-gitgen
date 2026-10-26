"""gitgen - git 변경 사항으로 커밋 메시지/PR 초안을 만드는 CLI.

스텝 1: Git 수집만 (API 호출 없음)
사용법: python gitgen.py commit
"""
import os
import subprocess
import sys


def run_git(*args):
    """git 명령을 실행하고 표준출력을 문자열로 돌려준다."""
    try:
        r = subprocess.run(
            ["git", *args],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",  # Windows 한글 깨짐 대비
        )
    except FileNotFoundError:
        sys.exit("[git 오류] git이 설치되어 있지 않거나 PATH에 없습니다")
    if r.returncode != 0:
        sys.exit(f"[git 오류] git {' '.join(args)}: {r.stderr.strip()}")
    return r.stdout


def ensure_repo_root():
    """Git 저장소의 루트 디렉토리에서 실행 중인지 확인한다."""
    top = run_git("rev-parse", "--show-toplevel").strip()
    if os.path.realpath(top) != os.path.realpath(os.getcwd()):
        sys.exit(f"[실행 위치 오류] 저장소 루트에서 실행하세요: {top}")


def collect_changes():
    """변경 파일 목록(status)과 변경 내용(diff)을 수집한다.

    staged 변경을 우선 사용하고, 없으면 unstaged 변경을 사용한다.
    """
    status = run_git("status", "--short")
    diff = run_git("diff", "--staged")
    source = "staged"
    if not diff.strip():
        diff = run_git("diff")
        source = "unstaged"
    return status, diff, source


def print_section(title, body):
    line = "=" * 50
    print(f"{line}\n[{title}]\n{line}\n{body.rstrip()}\n")


def main():
    if len(sys.argv) < 2 or sys.argv[1] != "commit":
        sys.exit("사용법: python gitgen.py commit")

    ensure_repo_root()
    status, diff, source = collect_changes()

    if not diff.strip():
        print("변경 사항이 없습니다")
        return

    print_section("변경 파일 (git status)", status)
    print_section(f"변경 내용 (git diff, {source})", diff)
    print(f"[log] diff {len(diff.splitlines())}줄 수집, API 호출 0회 (스텝 1)")


if __name__ == "__main__":
    main()
