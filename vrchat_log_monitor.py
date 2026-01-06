#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
VRChatログファイル監視モジュール
VRChatのログファイルを監視してプレイヤーの出入りを検知します
"""

import os
import re
import time
import logging
from pathlib import Path
from typing import Callable, Optional

logger = logging.getLogger(__name__)


class VRChatLogMonitor:
    """VRChatログファイル監視クラス"""
    
    # ログパターン
    PLAYER_JOINED_PATTERN = re.compile(
        r'\[.*?\]\s+.*?OnPlayerJoined\s+.*?displayName=([^\s,]+).*?id=([^\s,)]+)',
        re.IGNORECASE
    )
    PLAYER_LEFT_PATTERN = re.compile(
        r'\[.*?\]\s+.*?OnPlayerLeft\s+.*?displayName=([^\s,]+).*?id=([^\s,)]+)',
        re.IGNORECASE
    )
    
    # より簡易なパターン（実際のログ形式に応じて調整が必要）
    SIMPLE_JOIN_PATTERN = re.compile(
        r'OnPlayerJoined.*?displayName[=:]\s*([^\s,]+).*?id[=:]\s*([^\s,)]+)',
        re.IGNORECASE
    )
    SIMPLE_LEFT_PATTERN = re.compile(
        r'OnPlayerLeft.*?displayName[=:]\s*([^\s,]+).*?id[=:]\s*([^\s,)]+)',
        re.IGNORECASE
    )
    
    def __init__(self, log_file_path: Optional[str] = None):
        """
        初期化
        
        Args:
            log_file_path: VRChatログファイルのパス（Noneの場合は自動検出）
        """
        self.log_file_path = log_file_path or self._find_log_file()
        self.file_position = 0
        self.on_player_joined: Optional[Callable[[str, str], None]] = None
        self.on_player_left: Optional[Callable[[str, str], None]] = None
        
        if not self.log_file_path or not os.path.exists(self.log_file_path):
            logger.warning(f"VRChatログファイルが見つかりません: {self.log_file_path}")
            logger.info("VRChatを起動してから再度実行してください")
        else:
            logger.info(f"VRChatログファイルを監視します: {self.log_file_path}")
            # 既存のログは無視して、新しいログのみ監視
            self.file_position = os.path.getsize(self.log_file_path)
    
    def _find_log_file(self) -> Optional[str]:
        """VRChatログファイルを自動検出"""
        # Windowsの場合
        appdata = os.getenv('APPDATA')
        if appdata:
            log_path = Path(appdata).parent / 'LocalLow' / 'VRChat' / 'VRChat' / 'output_log.txt'
            if log_path.exists():
                return str(log_path)
        
        # 一般的なパス
        possible_paths = [
            os.path.expanduser("~/AppData/LocalLow/VRChat/VRChat/output_log.txt"),
            os.path.expanduser("~/.config/VRChat/VRChat/output_log.txt"),
        ]
        
        for path in possible_paths:
            if os.path.exists(path):
                return path
        
        return None
    
    def set_callbacks(self, 
                     on_joined: Optional[Callable[[str, str], None]] = None,
                     on_left: Optional[Callable[[str, str], None]] = None):
        """
        コールバック関数を設定
        
        Args:
            on_joined: プレイヤー参加時のコールバック (username, user_id)
            on_left: プレイヤー退出時のコールバック (username, user_id)
        """
        self.on_player_joined = on_joined
        self.on_player_left = on_left
    
    def _parse_log_line(self, line: str):
        """ログ行を解析してプレイヤー出入りを検知"""
        # 参加検知
        match = self.PLAYER_JOINED_PATTERN.search(line) or self.SIMPLE_JOIN_PATTERN.search(line)
        if match:
            username = match.group(1).strip()
            user_id = match.group(2).strip()
            logger.debug(f"プレイヤー参加検知: {username} ({user_id})")
            if self.on_player_joined:
                self.on_player_joined(username, user_id)
            return
        
        # 退出検知
        match = self.PLAYER_LEFT_PATTERN.search(line) or self.SIMPLE_LEFT_PATTERN.search(line)
        if match:
            username = match.group(1).strip()
            user_id = match.group(2).strip()
            logger.debug(f"プレイヤー退出検知: {username} ({user_id})")
            if self.on_player_left:
                self.on_player_left(username, user_id)
    
    def check_new_logs(self):
        """新しいログをチェック"""
        if not self.log_file_path or not os.path.exists(self.log_file_path):
            return
        
        try:
            with open(self.log_file_path, 'r', encoding='utf-8', errors='ignore') as f:
                # 前回の位置に移動
                f.seek(self.file_position)
                
                # 新しい行を読み込む
                new_lines = f.readlines()
                
                # 位置を更新
                self.file_position = f.tell()
                
                # 各行を解析
                for line in new_lines:
                    self._parse_log_line(line)
                    
        except Exception as e:
            logger.error(f"ログファイル読み込みエラー: {e}")
    
    def start_monitoring(self, interval: float = 0.5):
        """
        ログファイルの監視を開始（ブロッキング）
        
        Args:
            interval: チェック間隔（秒）
        """
        if not self.log_file_path or not os.path.exists(self.log_file_path):
            logger.error("ログファイルが見つかりません。監視を開始できません。")
            return
        
        logger.info("ログファイルの監視を開始しました")
        try:
            while True:
                self.check_new_logs()
                time.sleep(interval)
        except KeyboardInterrupt:
            logger.info("ログ監視を停止しました")



