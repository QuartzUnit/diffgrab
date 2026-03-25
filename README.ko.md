# diffgrab

[![PyPI](https://img.shields.io/pypi/v/diffgrab)](https://pypi.org/project/diffgrab/)
[![Python](https://img.shields.io/pypi/pyversions/diffgrab)](https://pypi.org/project/diffgrab/)
[![License](https://img.shields.io/github/license/QuartzUnit/diffgrab)](https://github.com/QuartzUnit/diffgrab/blob/main/LICENSE)

> [English](README.md)

웹 페이지 변경 감지 + 구조화된 diff. markgrab + snapgrab 통합, MCP 네이티브.

```python
from diffgrab import DiffTracker

tracker = DiffTracker()
await tracker.track("https://example.com")
changes = await tracker.check()
for c in changes:
    if c.changed:
        print(c.summary)     # "3 lines added, 1 lines removed in sections: Introduction."
        print(c.unified_diff) # 표준 unified diff 출력
await tracker.close()
```

## 기능

- **변경 감지** — URL을 추적하고 콘텐츠 해싱으로 변경 감지
- **구조화된 diff** — unified diff + 섹션 수준 분석 (어떤 헤딩이 변경됐는지)
- **사람이 읽기 쉬운 요약** — "5 lines added, 2 removed in sections: Intro, Methods"
- **스냅샷 이력** — SQLite 저장, 과거 버전 탐색 가능
- **markgrab 기반** — [markgrab](https://github.com/QuartzUnit/markgrab)으로 HTML/YouTube/PDF/DOCX 추출
- **시각적 diff** — [snapgrab](https://github.com/QuartzUnit/snapgrab)으로 스크린샷 비교 (선택)
- **MCP 서버** — Claude Code / MCP 클라이언트용 5개 도구
- **CLI 내장** — `diffgrab track`, `check`, `diff`, `history`, `untrack`

## 설치

```bash
pip install diffgrab
```

선택적 추가 기능:

```bash
pip install 'diffgrab[cli]'      # click + rich CLI
pip install 'diffgrab[visual]'   # snapgrab 시각적 diff
pip install 'diffgrab[mcp]'      # fastmcp MCP 서버
pip install 'diffgrab[all]'      # 전체
```

## 사용법

### Python API

```python
import asyncio
from diffgrab import DiffTracker

async def main():
    tracker = DiffTracker()

    # URL 추적 (초기 스냅샷 촬영)
    await tracker.track("https://example.com", interval_hours=12)

    # 변경사항 확인
    changes = await tracker.check()
    for change in changes:
        if change.changed:
            print(change.summary)
            print(change.unified_diff)

    # 특정 스냅샷 간 diff
    result = await tracker.diff("https://example.com", before_id=1, after_id=2)

    # 스냅샷 이력 조회
    history = await tracker.history("https://example.com", count=20)

    # 추적 중지
    await tracker.untrack("https://example.com")

    await tracker.close()

asyncio.run(main())
```

### CLI

```bash
# URL 추적
diffgrab track https://example.com --interval 12

# 모든 추적 URL 변경사항 확인
diffgrab check

# 특정 URL 확인
diffgrab check https://example.com

# 스냅샷 간 diff 보기
diffgrab diff https://example.com
diffgrab diff https://example.com --before 1 --after 3

# 스냅샷 이력 조회
diffgrab history https://example.com --count 20

# 추적 중지
diffgrab untrack https://example.com
```

### MCP 서버

Claude Code MCP 설정에 추가:

```json
{
  "mcpServers": {
    "diffgrab": {
      "command": "diffgrab-mcp",
      "args": []
    }
  }
}
```

**MCP 도구:**

| 도구 | 설명 |
|------|------|
| `track_url` | 변경 추적할 URL 등록 |
| `check_changes` | 추적 중인 URL의 변경사항 확인 |
| `get_diff` | 스냅샷 간 구조화된 diff 조회 |
| `get_history` | 스냅샷 이력 조회 |
| `untrack_url` | URL 추적 중지 |

## DiffResult

```python
@dataclass
class DiffResult:
    url: str                           # 추적 URL
    changed: bool                      # 콘텐츠 변경 여부
    added_lines: int                   # 추가된 라인 수
    removed_lines: int                 # 삭제된 라인 수
    changed_sections: list[str]        # 변경된 마크다운 헤딩
    unified_diff: str                  # 표준 unified diff
    summary: str                       # 사람이 읽기 쉬운 요약
    before_snapshot_id: int | None     # 이전 스냅샷 DB ID
    after_snapshot_id: int | None      # 이후 스냅샷 DB ID
    before_timestamp: str              # 이전 스냅샷 시간
    after_timestamp: str               # 이후 스냅샷 시간
```

## QuartzUnit 생태계

| 패키지 | 역할 | PyPI |
|--------|------|------|
| [markgrab](https://github.com/QuartzUnit/markgrab) | HTML/YouTube/PDF/DOCX → 마크다운 | `pip install markgrab` |
| [snapgrab](https://github.com/QuartzUnit/snapgrab) | URL → 스크린샷 + 메타데이터 | `pip install snapgrab` |
| [docpick](https://github.com/QuartzUnit/docpick) | OCR + LLM 문서 추출 | `pip install docpick` |
| [feedkit](https://github.com/QuartzUnit/feedkit) | RSS 피드 수집 | `pip install feedkit` |
| **diffgrab** | **웹 페이지 변경 추적** | `pip install diffgrab` |
| [browsegrab](https://github.com/QuartzUnit/browsegrab) | LLM용 브라우저 에이전트 | `pip install browsegrab` |

## 라이선스

[MIT](LICENSE)
