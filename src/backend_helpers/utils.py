"""
Utility functions for backend.
"""

import os
import tempfile
from pathlib import Path
import streamlit as st
from databricks.sdk import WorkspaceClient
from dotenv import load_dotenv

load_dotenv()


def get_workspace_client() -> WorkspaceClient:
    if "workspace_client" not in st.session_state:
        st.session_state.workspace_client = WorkspaceClient(
            host=os.environ["DATABRICKS_HOST"],
            token=os.environ["DATABRICKS_TOKEN"],
        )
    return st.session_state.workspace_client


def download_volume_tree(volume_path: str) -> str:
    """Mirror a UC Volume directory tree into a local temp dir so local-filesystem code can read it."""
    client = get_workspace_client()
    local_root = tempfile.mkdtemp(prefix="fcrm_volume_input_")
    volume_path = volume_path.rstrip("/")

    def walk(remote_dir: str, local_dir: str) -> None:
        for entry in client.files.list_directory_contents(remote_dir):
            local_target = os.path.join(local_dir, entry.name)
            if entry.is_directory:
                os.makedirs(local_target, exist_ok=True)
                walk(entry.path, local_target)
            else:
                with open(local_target, "wb") as target_file:
                    target_file.write(client.files.download(entry.path).contents.read())

    walk(volume_path, local_root)
    return local_root


def upload_local_tree(local_dir: str, volume_path: str) -> None:
    """Upload a local directory tree to a UC Volume path, preserving relative structure."""
    client = get_workspace_client()
    volume_path = volume_path.rstrip("/")
    for current_root, _dirs, files in os.walk(local_dir):
        relative_dir = os.path.relpath(current_root, local_dir)
        for filename in files:
            local_file = os.path.join(current_root, filename)
            remote_file = (
                f"{volume_path}/{filename}"
                if relative_dir == "."
                else f"{volume_path}/{relative_dir}/{filename}"
            )
            with open(local_file, "rb") as source_file:
                client.files.upload(remote_file, source_file, overwrite=True)


def volume_folder_exists(base_path: str, folder_name: str) -> bool:
    client = get_workspace_client()
    return any(
        entry.is_directory and entry.name.casefold() == folder_name.casefold()
        for entry in client.files.list_directory_contents(base_path.rstrip("/"))
    )


def download_volume_file(volume_path: str, local_path: Path) -> None:
    response = get_workspace_client().files.download(volume_path)
    local_path.write_bytes(response.contents.read())
