"""쇼핑 리스트 앱 (Streamlit)."""

from __future__ import annotations

import json
import re
import uuid
from pathlib import Path

import streamlit as st

DATA_FILE = Path(__file__).with_name("shopping_list.json")


# ---------- 저장 ----------
# 파일이 원본이다. 매 실행과 매 변경 직전에 다시 읽어서, 여러 탭이 서로의 변경을 덮어쓰지 않게 한다.

def load_items() -> list[dict]:
    """JSON 파일에서 목록을 불러온다 (없거나 깨졌으면 빈 목록, 중복 id는 새로 발급)."""
    try:
        data = json.loads(DATA_FILE.read_text(encoding="utf-8"))
        items = [
            {"id": str(d["id"]), "name": str(d["name"]), "checked": d["checked"] is True}
            for d in data
        ]
    except (OSError, ValueError, TypeError, KeyError):
        return []
    seen = set()
    for item in items:
        if item["id"] in seen:
            item["id"] = str(uuid.uuid4())
        seen.add(item["id"])
    return items


def save_items(items: list[dict]) -> None:
    """목록을 JSON 파일에 저장한다 (임시 파일에 쓴 뒤 교체해 파일이 깨지지 않게)."""
    tmp = DATA_FILE.with_suffix(".tmp")
    try:
        tmp.write_text(json.dumps(items, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(DATA_FILE)
    except OSError:
        st.session_state.message = ("error", "목록을 파일에 저장하지 못했어요.")


def sync_items() -> list[dict]:
    """파일에서 최신 목록을 읽어 세션 상태에 반영한다."""
    st.session_state.shopping_items = load_items()
    return st.session_state.shopping_items


# ---------- 상태 ----------

def init_state() -> None:
    """세션 상태를 초기화한다 (목록은 매번 파일에서 다시 읽음)."""
    sync_items()
    for key in ("editing_id", "message", "toast"):
        if key not in st.session_state:
            st.session_state[key] = None
    if st.session_state.editing_id and not find_item(st.session_state.editing_id):
        st.session_state.editing_id = None  # 다른 탭에서 삭제된 항목


# ---------- 기능 ----------

def find_item(item_id: str) -> dict | None:
    """id로 아이템을 찾아 반환한다 (없으면 None)."""
    return next((i for i in st.session_state.shopping_items if i["id"] == item_id), None)


def add_item(name: str) -> bool:
    """새 아이템을 목록 맨 아래에 추가한다 (추가했으면 True)."""
    name = name.strip()
    if not name:
        st.session_state.message = ("warning", "아이템 이름을 입력해주세요.")
        return False
    items = sync_items()
    items.append({"id": str(uuid.uuid4()), "name": name, "checked": False})
    save_items(items)
    return True


def update_item(item_id: str, new_name: str) -> None:
    """아이템 이름을 변경한다."""
    new_name = new_name.strip()
    if not new_name:
        st.session_state.message = ("warning", "빈 이름으로는 저장할 수 없어요.")
        return
    items = sync_items()
    item = find_item(item_id)
    if item:
        item["name"] = new_name
        save_items(items)
    st.session_state.editing_id = None


def delete_item(item_id: str) -> dict | None:
    """아이템을 삭제하고, 삭제한 아이템을 반환한다."""
    sync_items()
    item = find_item(item_id)
    items = [i for i in st.session_state.shopping_items if i["id"] != item_id]
    st.session_state.shopping_items = items
    if st.session_state.editing_id == item_id:
        st.session_state.editing_id = None
    save_items(items)
    return item


def toggle_item(item_id: str, checked: bool) -> None:
    """아이템의 구매 완료 여부를 체크박스 값으로 맞춘다."""
    items = sync_items()
    item = find_item(item_id)
    if item:
        item["checked"] = checked
        save_items(items)


def clear_checked() -> int:
    """완료된 아이템을 모두 삭제하고, 삭제한 개수를 반환한다."""
    items = sync_items()
    remaining = [i for i in items if not i["checked"]]
    st.session_state.shopping_items = remaining
    if st.session_state.editing_id and not find_item(st.session_state.editing_id):
        st.session_state.editing_id = None
    save_items(remaining)
    return len(items) - len(remaining)


# ---------- 위젯 콜백 ----------

def notify(text: str) -> None:
    """다음 화면 갱신 때 띄울 토스트 알림을 예약한다."""
    st.session_state.toast = text


def on_add_submit() -> None:
    name = st.session_state.new_item_name.strip()
    if add_item(name):
        notify(f"'{escape_md(name)}'을(를) 추가했어요")


def on_delete(item_id: str) -> None:
    item = delete_item(item_id)
    if item:
        notify(f"'{escape_md(item['name'])}'을(를) 삭제했어요")


def on_clear_checked() -> None:
    notify(f"완료 항목 {clear_checked()}개를 삭제했어요")


def on_toggle(item_id: str) -> None:
    toggle_item(item_id, st.session_state[f"chk_{item_id}"])


def start_edit(item_id: str) -> None:
    st.session_state.editing_id = item_id


def cancel_edit() -> None:
    st.session_state.editing_id = None


def on_edit_save(item_id: str) -> None:
    update_item(item_id, st.session_state[f"edit_{item_id}"])


# ---------- 화면 ----------

CSS = """
<style>
/* 완료 항목: 취소선 + 회색 */
del { color: #9e9e9e; }
/* 항목 이름 세로 가운데 정렬, 구분선 간격 축소 */
[data-testid="stColumn"] [data-testid="stMarkdownContainer"] p { margin-bottom: 0; }
hr { margin: 0.25rem 0 !important; }
/* 버튼 문구 줄바꿈 방지 */
.stButton button p, .stFormSubmitButton button p { white-space: nowrap; }
/* 좁은 화면에서도 한 줄 배치 유지 (Streamlit은 640px 미만에서 열을 세로로 쌓음) */
@media (max-width: 640px) {
    [data-testid="stHorizontalBlock"] { flex-wrap: nowrap !important; gap: 0.5rem !important; }
    [data-testid="stHorizontalBlock"] > [data-testid="stColumn"] { min-width: 0 !important; }
}
/* 아주 좁은 화면에서는 버튼 문구를 숨기고 아이콘만 표시 */
@media (max-width: 480px) {
    .stButton button [data-testid="stMarkdownContainer"],
    .stFormSubmitButton button [data-testid="stMarkdownContainer"] { display: none; }
    /* 일괄 삭제는 아이콘만으로 뜻이 불분명하므로 문구 유지 */
    .st-key-clear_area button [data-testid="stMarkdownContainer"] { display: block; }
}
</style>
"""


def escape_md(text: str) -> str:
    """사용자 입력이 마크다운으로 해석되지 않도록 이스케이프한다."""
    return re.sub(r"([\\`*_{}\[\]()#+\-.!~|<>])", r"\\\1", text)


def render_item(item: dict) -> None:
    """아이템 한 줄을 그린다 (수정 중이면 입력창으로)."""
    item_id = item["id"]
    name = escape_md(item["name"])
    # 다른 탭에서 바뀐 체크 상태도 반영되도록 위젯 값을 파일 값에 맞춘다
    st.session_state[f"chk_{item_id}"] = item["checked"]
    col_chk, col_rest = st.columns([0.1, 0.9], vertical_alignment="center")
    col_chk.checkbox(
        f"{name} 완료", key=f"chk_{item_id}",
        on_change=on_toggle, args=(item_id,), label_visibility="collapsed",
    )
    with col_rest:
        if st.session_state.editing_id == item_id:
            # form 안에 두어 Enter로도 저장되게 한다
            with st.form(f"edit_form_{item_id}", border=False):
                col_name, col_a, col_b = st.columns([0.66, 0.17, 0.17], vertical_alignment="center")
                col_name.text_input(
                    "이름 수정", value=item["name"], key=f"edit_{item_id}",
                    label_visibility="collapsed",
                )
                col_a.form_submit_button("저장", icon="💾", on_click=on_edit_save, args=(item_id,))
                col_b.form_submit_button("취소", icon="↩", on_click=cancel_edit)
        else:
            col_name, col_a, col_b = st.columns([0.66, 0.17, 0.17], vertical_alignment="center")
            col_name.markdown(f"~~{name}~~" if item["checked"] else name)
            col_a.button("수정", icon="✏️", key=f"editbtn_{item_id}", on_click=start_edit, args=(item_id,))
            col_b.button("삭제", icon="🗑️", key=f"del_{item_id}", on_click=on_delete, args=(item_id,))


def main() -> None:
    st.set_page_config(page_title="쇼핑 리스트", page_icon="🛒")
    init_state()
    st.markdown(CSS, unsafe_allow_html=True)
    items = st.session_state.shopping_items

    if st.session_state.toast:
        st.toast(st.session_state.toast)
        st.session_state.toast = None

    # ----- 상단: 제목 + 진행 현황 -----
    st.title("🛒 쇼핑 리스트")
    total = len(items)
    done = sum(i["checked"] for i in items)
    st.write(f"전체 {total}개 중 {done}개 완료")
    if total:
        st.progress(done / total)

    # ----- 입력 영역 -----
    with st.form("add_form", clear_on_submit=True):
        col_input, col_btn = st.columns([0.8, 0.2], vertical_alignment="center")
        col_input.text_input(
            "아이템", key="new_item_name", label_visibility="collapsed",
            placeholder="살 물건을 입력하세요 (예: 우유)",
        )
        col_btn.form_submit_button("추가", icon="➕", on_click=on_add_submit, width="stretch")

    if st.session_state.message:
        level, text = st.session_state.message
        getattr(st, level)(text)
        st.session_state.message = None

    # ----- 목록 영역: 미완료 먼저, 완료는 아래 (저장 순서는 유지) -----
    if not items:
        st.info("아직 항목이 없습니다.")
    for idx, item in enumerate(sorted(items, key=lambda i: i["checked"])):
        if idx:
            st.divider()
        render_item(item)

    # ----- 하단 영역 -----
    with st.container(horizontal=True, horizontal_alignment="right", key="clear_area"):
        st.button("완료 항목 삭제", icon="🧹", on_click=on_clear_checked, disabled=done == 0)


main()
