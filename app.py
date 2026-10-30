from pathlib import Path

import streamlit as st

from ecoprune.review import (
    build_preview,
    group_key,
    is_protected_path,
    parse_protected_folders,
    relative_file_path,
)
from ecoprune.scanner import scan_folder


def _clear_choice_widgets(clear_protection: bool = False) -> None:
    for key in list(st.session_state):
        if key.startswith(("keeper:", "candidate:", "necessary:")):
            st.session_state.pop(key, None)
    st.session_state.pop("selection_preview", None)
    st.session_state.pop("scan_result", None)
    st.session_state.pop("scan_error", None)
    if clear_protection:
        st.session_state["protected_folders"] = ""


def _folder_changed() -> None:
    _clear_choice_widgets(clear_protection=True)


def _protected_folders_changed() -> None:
    for key in list(st.session_state):
        if key.startswith("candidate:"):
            st.session_state.pop(key, None)
    st.session_state.pop("selection_preview", None)


def _clear_group_candidates(group_id: str) -> None:
    prefix = f"candidate:{group_id}:"
    for key in list(st.session_state):
        if key.startswith(prefix):
            st.session_state.pop(key, None)


st.set_page_config(page_title="EcoPrune | Kopya İnceleme", page_icon="🌿", layout="wide")
st.title("🌿 EcoPrune")
st.caption("Kesin içerik kopyalarını inceleyin ve işlem önizlemesi hazırlayın.")

default_folder = str(Path(__file__).parent / "demo")
if "folder_input" not in st.session_state:
    st.session_state["folder_input"] = default_folder
folder = st.text_input(
    "Taranacak klasör",
    key="folder_input",
    help="Taramak istediğiniz yerel klasörün tam yolunu girin.",
    on_change=_folder_changed,
)
protected_text = st.text_area(
    "Korunan klasörler (kök dizine göre, her satıra bir yol)",
    key="protected_folders",
    help="Bu klasörlerdeki dosyalar görünür; işlem adayı olarak seçilemez. Örnek: Arsiv\\Onemli",
    on_change=_protected_folders_changed,
)

if st.button("Klasörü tara", type="primary", on_click=_clear_choice_widgets):
    try:
        with st.spinner("Dosyalar inceleniyor… SHA-256 ve içerik doğrulaması sürüyor."):
            st.session_state["scan_result"] = scan_folder(folder)
            st.session_state["scan_error"] = None
    except (OSError, ValueError) as exc:
        st.session_state["scan_error"] = str(exc)
        st.session_state.pop("scan_result", None)

if st.session_state.get("scan_error"):
    st.error(f"Klasör taranamadı: {st.session_state['scan_error']}")

result = st.session_state.get("scan_result")
if not result:
    st.info("İncelemeyi başlatmak için bir klasör seçip tarayın.")
else:
    try:
        protected_folders = parse_protected_folders(protected_text)
        protected_input_error = None
    except ValueError as exc:
        protected_folders = ()
        protected_input_error = str(exc)
        st.error(f"Korunan klasör yolu geçersiz: {exc}")

    total_reducible = sum(group.recoverable_logical_bytes for group in result.duplicate_groups)
    a, b, c = st.columns(3)
    a.metric("Taranan dosya", f"{result.files_scanned:,}")
    b.metric("Toplam mantıksal boyut", f"{result.logical_bytes:,} bayt")
    c.metric("Azaltılabilecek mantıksal veri", f"{total_reducible:,} bayt")
    st.caption(
        "Toplam mantıksal boyut, hard linklerle aynı dosyanın yeniden sayılması hariç "
        "taranan dosya boyutlarının toplamıdır; ayrı kopyalar bu toplama dahildir. "
        "Azaltılabilecek mantıksal veri, her grupta bir kopya korunursa tekrar eden boyutların tahminidir. "
        "Bunlar fiziksel disk veya karbon tasarrufu ölçümü değildir."
    )

    if result.duplicate_groups:
        st.subheader("Kopya grupları")
        keepers: dict[str, str] = {}
        selected_candidates: set[tuple[str, str]] = set()
        necessary_groups: set[str] = set()

        for index, group in enumerate(result.duplicate_groups, start=1):
            key = group_key(result.root, group)
            paths = [relative_file_path(result.root, file) for file in group.files]
            files_by_path = dict(zip(paths, group.files))
            with st.expander(
                f"Grup {index} · {len(group.files)} dosya · "
                f"azaltılabilecek mantıksal veri {group.recoverable_logical_bytes:,} bayt",
                expanded=True,
            ):
                for relative_path, file in files_by_path.items():
                    protected = is_protected_path(relative_path, protected_folders)
                    label = " · korunan klasör" if protected else ""
                    st.text(f"{relative_path} · {file.size:,} bayt{label}")

                keeper = st.selectbox(
                    "Korunacak dosya",
                    options=paths,
                    key=f"keeper:{key}",
                    on_change=_clear_group_candidates,
                    args=(key,),
                    format_func=lambda path, size_map={p: f.size for p, f in files_by_path.items()}
                    : f"{path} · {size_map[path]:,} bayt",
                )
                keepers[key] = keeper

                necessary = st.checkbox(
                    "Bu kopyalar gerekli (bu taramada işlem dışında bırak)",
                    key=f"necessary:{key}",
                    on_change=_clear_group_candidates,
                    args=(key,),
                )
                if necessary:
                    necessary_groups.add(key)

                for relative_path, file in files_by_path.items():
                    protected = is_protected_path(relative_path, protected_folders)
                    is_keeper = relative_path == keeper
                    st.checkbox(
                        f"İşlem adayı: {relative_path} · {file.size:,} bayt",
                        key=f"candidate:{key}:{relative_path}",
                        value=False,
                        disabled=(is_keeper or protected or necessary or protected_input_error is not None),
                        help=(
                            "Korunan klasörde bulunduğu için seçilemez."
                            if protected else "Korunacak dosya aday olamaz."
                            if is_keeper else "Bu grup bu tarama için işlem dışında."
                            if necessary else None
                        ),
                    )
                    if st.session_state.get(f"candidate:{key}:{relative_path}", False):
                        selected_candidates.add((key, relative_path))

        preview = build_preview(
            result,
            keepers,
            selected_candidates,
            necessary_groups,
            protected_folders,
        )
        st.subheader("İşlem önizlemesi")
        st.caption("Bu önizleme yalnızca seçimi ve boyutları gösterir; hiçbir dosya taşınmaz veya silinmez.")
        if protected_input_error:
            st.error("Korunan klasör yollarını düzeltmeden önizleme geçerli olmaz.")
        for error in preview.errors:
            st.error(error)

        if preview.valid and not protected_input_error:
            left, right = st.columns(2)
            left.metric("Seçilen işlem adayı", len(preview.candidates))
            right.metric("Adayların toplam mantıksal boyutu", f"{preview.candidate_logical_bytes:,} bayt")
            for group_preview in preview.groups:
                if group_preview.necessary:
                    st.write(f"**Hariç:** Grup {group_preview.key} — Bu kopyalar gerekli")
                st.text(f"Korunacak: {group_preview.keeper_path}")
                for path in group_preview.candidate_paths:
                    size = next(file.size for file in group_preview.files if file.relative_path == path)
                    st.text(f"Aday: {path} · {size:,} bayt")
            if not preview.candidates:
                st.info("Henüz işlem adayı seçilmedi.")
        else:
            st.info("Seçim kurallarını düzeltip önizlemeyi yeniden kontrol edin.")
    else:
        st.info("Kesin içerik kopyası bulunamadı.")

    if result.skipped_hard_links:
        st.caption(f"Aynı fiziksel dosyaya bağlı {result.skipped_hard_links} hard link ayrıca sayılmadı.")
    if result.issues:
        st.subheader(f"Uyarılar ve atlanan öğeler ({len(result.issues)})")
        for issue in result.issues:
            st.warning(issue)
