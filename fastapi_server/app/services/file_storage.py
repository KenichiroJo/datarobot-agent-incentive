# Copyright 2026 DataRobot, Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#   http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
"""コミッション用アップロードファイルのローカル保存ヘルパー。

モック実装のため `.data/uploads/{session_id}/` に保存する。production では
``core.persistent_fs.dr_file_system`` を介して AI Catalog に保存できるが、
本モックでは触れない。
"""
from __future__ import annotations

import logging
import re
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import BinaryIO

logger = logging.getLogger(__name__)

# 受付可能拡張子
_ALLOWED_SUFFIXES = {".xlsx", ".xls", ".csv"}

# パストラバーサル対策
_SAFE_NAME_RE = re.compile(r"[^A-Za-z0-9._\-]+")


@dataclass(frozen=True)
class StoredFile:
    """保存済みファイルのメタデータ。"""

    file_id: str
    filename: str
    safe_filename: str  # ストレージ上の実ファイル名 (sanitize 済み)
    path: Path
    size: int
    detected_type: str  # 'sales' | 'master' | 'unknown'


def _sanitize_filename(name: str) -> str:
    """ファイル名を path-safe にする。日本語は保持（Path セーフ）、危険文字を `_` に置換。"""
    # path separator や絶対パス指定を除去
    base = Path(name).name
    # Windows 予約文字 / 制御文字を除去
    safe = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", base)
    # 連続するドットや空白を整理
    safe = re.sub(r"\.+", ".", safe).strip("._ ")
    return safe or f"upload-{uuid.uuid4().hex[:8]}"


def detect_file_type(filename: str) -> str:
    """ファイル名から種別を判定する。

    "売上明細" or "売上" を含む → "sales"
    "取引条件" or "マスタ" を含む → "master"
    それ以外は "unknown"
    """
    name = filename
    if "売上明細" in name or "売上" in name:
        return "sales"
    if "取引条件" in name or "マスタ" in name or "master" in name.lower():
        return "master"
    return "unknown"


class CommissionFileStorage:
    """session_id 配下にファイルを保存する単純な disk-backed store。"""

    def __init__(self, base_dir: Path | str) -> None:
        self._base_dir = Path(base_dir)
        self._base_dir.mkdir(parents=True, exist_ok=True)
        logger.info("CommissionFileStorage initialized base_dir=%s", self._base_dir)

    def session_dir(self, session_id: str) -> Path:
        # session_id にも path-safe sanitize を念のため適用
        safe_session = _SAFE_NAME_RE.sub("_", session_id) or "default"
        d = self._base_dir / safe_session
        d.mkdir(parents=True, exist_ok=True)
        return d

    def save(
        self,
        session_id: str,
        original_filename: str,
        source: BinaryIO,
        max_bytes: int | None = None,
    ) -> StoredFile:
        """ファイルを保存して StoredFile を返す。

        Raises:
            ValueError: 拡張子が不許可 / サイズが上限超過の場合
        """
        suffix = Path(original_filename).suffix.lower()
        if suffix not in _ALLOWED_SUFFIXES:
            raise ValueError(
                f"許可されていない拡張子です: {suffix} (許可: {sorted(_ALLOWED_SUFFIXES)})"
            )

        safe_name = _sanitize_filename(original_filename)
        file_id = uuid.uuid4().hex
        # ID をファイル名前に付与して衝突を避ける
        stored_name = f"{file_id}_{safe_name}"
        target_path = self.session_dir(session_id) / stored_name

        # ストリーミングで保存しつつサイズチェック
        total = 0
        chunk_size = 1 << 20  # 1MiB
        with target_path.open("wb") as out:
            while True:
                chunk = source.read(chunk_size)
                if not chunk:
                    break
                total += len(chunk)
                if max_bytes is not None and total > max_bytes:
                    out.close()
                    try:
                        target_path.unlink(missing_ok=True)
                    except OSError:
                        pass
                    raise ValueError(
                        f"ファイルサイズが上限 {max_bytes:,} bytes を超えました: {original_filename}"
                    )
                out.write(chunk)

        detected = detect_file_type(original_filename)
        logger.info(
            "ファイル保存: session=%s name=%s size=%d type=%s -> %s",
            session_id,
            original_filename,
            total,
            detected,
            target_path,
        )

        return StoredFile(
            file_id=file_id,
            filename=original_filename,
            safe_filename=stored_name,
            path=target_path,
            size=total,
            detected_type=detected,
        )

    def delete_session(self, session_id: str) -> None:
        """session 内の全ファイルを削除する。"""
        d = self.session_dir(session_id)
        for p in d.iterdir():
            try:
                p.unlink()
            except OSError:
                logger.warning("ファイル削除失敗: %s", p)
        try:
            d.rmdir()
        except OSError:
            pass
