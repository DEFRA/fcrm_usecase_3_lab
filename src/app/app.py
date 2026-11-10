import os
import streamlit as st
from dotenv import load_dotenv
import mammoth
from backend_helpers.utils import download_volume_tree

load_dotenv()

FORMS_PATH = "/Volumes/prd_dash_lab/ea_fcrm_ai_labs/ai_labs/UC3/Forms"

# Height (px) of the side-by-side document / review panes. Each pane scrolls
# independently once its content exceeds this height.
PANE_HEIGHT = 700

# Page config
st.set_page_config(
    layout="wide",
    page_title="PROTOTYPE - FCRM Moderation Agent"
)
st.title("FCRM Moderation Agent Prototype")

# Footer
st.markdown(
    """
    <style>
        .block-container { padding-bottom: 4rem; }
        .custom-footer {
            position: fixed;
            bottom: 0;
            left: 0;
            width: 100%;
            background-color: #e0e0e0;
            color: #808080;
            text-align: center;
            padding: 10px 0;
            font-size: 13px;
            z-index: 9999;
            border-top: 1px solid #ddd;
        }
    </style>
    <div class="custom-footer">
        This tool is AI and can make mistakes. Always verify AI-generated information.
    </div>
    """,
    unsafe_allow_html=True,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def list_docx_files(root: str) -> list[str]:
    """Return all .docx files under root as relative paths, in a stable order.

    This single ordered list drives BOTH the file list view and the
    Next/Previous navigation, so the two always agree.
    """
    files = []
    for current, dirs, names in os.walk(root):
        dirs.sort(key=str.casefold)  # in-place sort controls walk order
        for name in sorted(names, key=str.casefold):
            # skip Word lock/temp files such as "~$form.docx"
            if name.lower().endswith(".docx") and not name.startswith("~$"):
                files.append(os.path.relpath(os.path.join(current, name), root))
    return files


@st.cache_data(show_spinner=False)
def docx_to_html(path: str) -> str:
    """Convert a .docx file to an HTML string (cached per path)."""
    with open(path, "rb") as docx_file:
        result = mammoth.convert_to_html(docx_file)
    return result.value


def load_files(force: bool = False) -> None:
    """Download the volume once per session and cache the file list."""
    if force:
        st.session_state.pop("local_root", None)
        st.session_state.pop("files", None)
        st.session_state.current_index = None
    if "local_root" not in st.session_state:
        with st.spinner("Fetching file structure from Databricks..."):
            root = download_volume_tree(FORMS_PATH)
            st.session_state.local_root = root
            st.session_state.files = list_docx_files(root)


def open_file(index: int) -> None:
    st.session_state.current_index = index


def go_previous() -> None:
    st.session_state.current_index -= 1


def go_next() -> None:
    st.session_state.current_index += 1


def go_back() -> None:
    st.session_state.current_index = None


def nav_bar(position: str, index: int, total: int) -> None:
    """Back / Previous / Next buttons. `position` keeps widget keys unique."""
    back_col, prev_col, next_col, _ = st.columns([1.2, 1, 1, 6])
    back_col.button("⬅ Back to list", key=f"back_{position}", on_click=go_back)
    prev_col.button(
        "◀ Previous",
        key=f"prev_{position}",
        on_click=go_previous,
        disabled=index <= 0,
    )
    next_col.button(
        "Next ▶",
        key=f"next_{position}",
        on_click=go_next,
        disabled=index >= total - 1,
    )


# ---------------------------------------------------------------------------
# State
# ---------------------------------------------------------------------------
if "current_index" not in st.session_state:
    st.session_state.current_index = None

try:
    load_files()
except Exception as e:
    st.error(f"An error occurred while fetching the file structure: {e}")
    st.stop()

files: list[str] = st.session_state.files
local_root: str = st.session_state.local_root

# ---------------------------------------------------------------------------
# Document view
# ---------------------------------------------------------------------------
index = st.session_state.current_index
if index is not None and 0 <= index < len(files):
    rel_path = files[index]

    st.header(os.path.basename(rel_path))
    st.caption(f"{rel_path}  ·  file {index + 1} of {len(files)}")
    nav_bar("top", index, len(files))

    doc_col, review_col = st.columns(2, gap="medium")

    # Each column gets its own fixed-height, independently scrollable container
    with doc_col:
        with st.container(height=PANE_HEIGHT, border=True):
            st.subheader("Moderation Bid Form", )
            try:
                html = docx_to_html(os.path.join(local_root, rel_path))
                # Minimal styling so tables render sensibly; st.html renders the
                # HTML properly (unlike st.markdown, which mangles block-level HTML)
                st.html(
                    """
                    <style>
                        .docx-view table { border-collapse: collapse; margin: 0.5rem 0; }
                        .docx-view td, .docx-view th { border: 1px solid #888; padding: 4px 8px; }
                        .docx-view img { max-width: 100%; }
                    </style>
                    <div class="docx-view">""" + html + "</div>"
                )
            except Exception as e:
                st.error(f"Could not display this document: {e}")

    with review_col:
        with st.container(height=PANE_HEIGHT, border=True):
            st.subheader("AI-Generated Review")
            st.write("placeholder text")
            # Insert AI-generated review content here
            # ...

    st.divider()
    nav_bar("bottom", index, len(files))

# ---------------------------------------------------------------------------
# File list view
# ---------------------------------------------------------------------------
else:
    st.session_state.current_index = None
    st.header("File Structure View")
    st.button("🔄 Refresh from Databricks", on_click=load_files, kwargs={"force": True})

    if not files:
        st.info("No .docx files found in this folder.")

    last_folder = None
    for i, rel_path in enumerate(files):
        folder = os.path.dirname(rel_path)
        if folder != last_folder:
            if folder:
                depth = folder.count(os.sep)
                st.markdown(f"{'&nbsp;' * 4 * depth}📁 **{os.path.basename(folder)}**")
            last_folder = folder
        st.button(
            f"📄 {os.path.basename(rel_path)}",
            key=f"open_{i}",
            on_click=open_file,
            args=(i,),
        )