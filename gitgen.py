"""gitgen - git 변경 사항으로 커밋 메시지/PR 초안을 만드는 CLI.

스텝 1: Git 수집 (commit)
스텝 2: AI API 단독 호출 확인 (ping)
사용법: python gitgen.py commit | python gitgen.py ping
"""
import json
import os
import subprocess
import sys
import urllib.error
import urllib.request

# --- AI API 설정 ---
# 주소와 모델은 환경변수로 바꿀 수 있다 (기관 서버 등). 없으면 아래 기본값을 쓴다.
API_URL = os.environ.get("GITGEN_API_URL", "https://api.anthropic.com/v1/messages")
API_KEY_ENV = "ANTHROPIC_API_KEY"
API_VERSION = "2023-06-01"
DEFAULT_MODEL = os.environ.get("GITGEN_MODEL", "claude-haiku-5-5")
DEFAULT_TEMPERATURE = 0.3
DEFAULT_MAX_TOKENS = 300
TIMEOUT_SEC = 30


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


def call_ai(prompt, model=DEFAULT_MODEL, temperature=DEFAULT_TEMPERATURE,
            max_tokens=DEFAULT_MAX_TOKENS):
    """AI API를 1회 호출해 응답 텍스트를 돌려준다. 키는 환경변수에서만 읽는다."""
    key = os.environ.get(API_KEY_ENV)
    if not key:
        sys.exit(f"[설정 오류] 환경변수 {API_KEY_ENV}가 없습니다.\n"
                 f"  zsh/bash   : export {API_KEY_ENV}=\"키\"\n"
                 f"  PowerShell : $env:{API_KEY_ENV}=\"키\"")

    body = json.dumps({
        "model": model,
        "max_tokens": max_tokens,
        "temperature": temperature,
        "messages": [{"role": "user", "content": prompt}],
    }).encode("utf-8")
    req = urllib.request.Request(
        API_URL, data=body, method="POST",
        headers={
            "x-api-key": key,
            "anthropic-version": API_VERSION,
            "content-type": "application/json",
        },
    )

    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT_SEC) as res:
            data = json.load(res)
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", errors="replace")
        hint = {401: "API Key가 올바른지 확인하세요",
                403: "이 키로 해당 모델/기능을 쓸 권한이 없습니다",
                404: "모델 이름이 올바른지 확인하세요",
                429: "요청이 너무 많거나 한도를 넘었습니다. 잠시 후 다시 시도하세요"}.get(e.code, "")
        sys.exit(f"[API 오류 {e.code}] {hint}\n{detail}".rstrip())
    except urllib.error.URLError as e:
        sys.exit(f"[네트워크 오류] 서버에 연결할 수 없습니다: {e.reason}")
    except TimeoutError:
        sys.exit(f"[네트워크 오류] {TIMEOUT_SEC}초 안에 응답이 오지 않았습니다")

    try:
        text = "".join(b["text"] for b in data["content"] if b.get("type") == "text")
    except (KeyError, TypeError):
        sys.exit(f"[응답 형식 오류] 예상하지 못한 응답입니다: {str(data)[:300]}")

    print(f"[log] API 호출 1회 (url={API_URL}, model={model}, "
          f"temperature={temperature}, max_tokens={max_tokens})")
    return text.strip()


def print_section(title, body):
    line = "=" * 50
    print(f"{line}\n[{title}]\n{line}\n{body.rstrip()}\n")


def cmd_ping():
    """git 없이 API 연결만 확인한다 (스텝 2)."""
    answer = call_ai("한 문장으로 짧게 인사해줘.")
    print_section("API 응답", answer)


def main():
    if len(sys.argv) >= 2 and sys.argv[1] == "ping":
        return cmd_ping()
    if len(sys.argv) < 2 or sys.argv[1] != "commit":
        sys.exit("사용법: python gitgen.py commit | python gitgen.py ping")

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
