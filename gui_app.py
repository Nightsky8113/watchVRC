#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
V睡録画ソフト - GUIアプリケーション
"""

import customtkinter as ctk
import logging
import sys
import threading
import queue
import os
import re
import subprocess
import platform
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

from main import VRChatRecordingController

# CustomTkinterのテーマ設定
ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

# ログ設定（GUI用）
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('vrchat_recording.log', encoding='utf-8')
    ]
)
logger = logging.getLogger(__name__)


class LogHandler(logging.Handler):
    """GUI用のログハンドラー"""
    def __init__(self, log_queue):
        super().__init__()
        self.log_queue = log_queue
    
    def emit(self, record):
        self.log_queue.put(self.format(record))


class VRChatRecordingGUI:
    """V睡録画ソフトのGUIアプリケーション"""
    
    def __init__(self):
        self.root = ctk.CTk()
        self.root.title("V睡録画ソフト")
        self.root.geometry("900x700")
        
        self.controller: Optional[VRChatRecordingController] = None
        self.controller_thread: Optional[threading.Thread] = None
        self.is_running = False
        
        # ログキュー
        self.log_queue = queue.Queue()
        log_handler = LogHandler(self.log_queue)
        log_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
        logging.getLogger().addHandler(log_handler)
        
        self._create_widgets()
        self._start_log_updater()
        
    def _create_widgets(self):
        """ウィジェットを作成"""
        # メインフレーム
        main_frame = ctk.CTkFrame(self.root)
        main_frame.pack(fill="both", expand=True, padx=10, pady=10)
        
        # タイトル
        title_label = ctk.CTkLabel(
            main_frame,
            text="V睡録画ソフト",
            font=ctk.CTkFont(size=24, weight="bold")
        )
        title_label.pack(pady=(10, 20))
        
        # ステータスフレーム
        status_frame = ctk.CTkFrame(main_frame)
        status_frame.pack(fill="x", padx=20, pady=10)
        
        # 録画状態表示
        self.status_label = ctk.CTkLabel(
            status_frame,
            text="● 停止中",
            font=ctk.CTkFont(size=16),
            text_color="gray"
        )
        self.status_label.pack(side="left", padx=10, pady=10)
        
        # プレイヤー数表示
        self.player_count_label = ctk.CTkLabel(
            status_frame,
            text="プレイヤー数: 0",
            font=ctk.CTkFont(size=14)
        )
        self.player_count_label.pack(side="left", padx=10, pady=10)
        
        # OBS接続状態表示
        self.obs_status_label = ctk.CTkLabel(
            status_frame,
            text="OBS: 未接続",
            font=ctk.CTkFont(size=14),
            text_color="gray"
        )
        self.obs_status_label.pack(side="left", padx=10, pady=10)
        
        # OBS接続テストボタン
        self.obs_test_button = ctk.CTkButton(
            status_frame,
            text="OBS接続テスト",
            command=self._test_obs_connection,
            font=ctk.CTkFont(size=12),
            width=120,
            height=30
        )
        self.obs_test_button.pack(side="left", padx=5, pady=10)
        
        # コントロールボタンフレーム
        control_frame = ctk.CTkFrame(main_frame)
        control_frame.pack(fill="x", padx=20, pady=10)
        
        self.start_button = ctk.CTkButton(
            control_frame,
            text="監視開始",
            command=self._start_monitoring,
            font=ctk.CTkFont(size=14),
            width=120,
            height=40
        )
        self.start_button.pack(side="left", padx=5)
        
        self.stop_button = ctk.CTkButton(
            control_frame,
            text="監視停止",
            command=self._stop_monitoring,
            font=ctk.CTkFont(size=14),
            width=120,
            height=40,
            state="disabled"
        )
        self.stop_button.pack(side="left", padx=5)
        
        self.settings_button = ctk.CTkButton(
            control_frame,
            text="設定",
            command=self._open_settings,
            font=ctk.CTkFont(size=14),
            width=120,
            height=40
        )
        self.settings_button.pack(side="left", padx=5)
        
        self.exclude_button = ctk.CTkButton(
            control_frame,
            text="除外ユーザー管理",
            command=self._open_exclude_manager,
            font=ctk.CTkFont(size=14),
            width=150,
            height=40
        )
        self.exclude_button.pack(side="left", padx=5)
        
        # タブビュー
        tabview = ctk.CTkTabview(main_frame)
        tabview.pack(fill="both", expand=True, padx=20, pady=10)
        
        # プレイヤーリストタブ
        players_tab = tabview.add("プレイヤーリスト")
        self._create_players_tab(players_tab)
        
        # ログタブ
        log_tab = tabview.add("ログ")
        self._create_log_tab(log_tab)
        
    def _create_players_tab(self, parent):
        """プレイヤーリストタブを作成"""
        # スクロール可能なフレーム
        scrollable_frame = ctk.CTkScrollableFrame(parent)
        scrollable_frame.pack(fill="both", expand=True, padx=10, pady=10)
        
        self.players_frame = scrollable_frame
        self.player_widgets: Dict[str, ctk.CTkFrame] = {}
        
        # 初期メッセージ
        self.no_players_label = ctk.CTkLabel(
            scrollable_frame,
            text="プレイヤーがいません",
            font=ctk.CTkFont(size=14),
            text_color="gray"
        )
        self.no_players_label.pack(pady=20)
        
    def _create_log_tab(self, parent):
        """ログタブを作成"""
        # ログテキストボックス
        self.log_text = ctk.CTkTextbox(parent, font=ctk.CTkFont(family="Consolas", size=11))
        self.log_text.pack(fill="both", expand=True, padx=10, pady=10)
        
        # 録画ファイルパスのタグ設定（クリック可能にする）
        self.log_text.tag_config("file_path", foreground="cyan", underline=True)
        self.log_text.tag_bind("file_path", "<Button-1>", self._on_file_path_click)
        self.log_text.tag_bind("file_path", "<Enter>", lambda e: self.log_text.config(cursor="hand2"))
        self.log_text.tag_bind("file_path", "<Leave>", lambda e: self.log_text.config(cursor=""))
        
        # ボタンフレーム
        button_frame = ctk.CTkFrame(parent)
        button_frame.pack(fill="x", padx=10, pady=5)
        
        # クリアボタン
        clear_button = ctk.CTkButton(
            button_frame,
            text="ログをクリア",
            command=lambda: self.log_text.delete("1.0", "end"),
            width=120,
            height=30
        )
        clear_button.pack(side="left", padx=5)
        
        # 録画フォルダを開くボタン
        open_folder_button = ctk.CTkButton(
            button_frame,
            text="録画フォルダを開く",
            command=self._open_recording_folder,
            width=150,
            height=30
        )
        open_folder_button.pack(side="left", padx=5)
        
    def _start_log_updater(self):
        """ログ更新を開始"""
        def update_logs():
            while True:
                try:
                    log_message = self.log_queue.get(timeout=0.1)
                    # 録画ファイルパスを検出
                    file_paths = self._extract_file_paths(log_message)
                    
                    if file_paths:
                        # ファイルパスをタグ付けして挿入
                        start_pos = self.log_text.index("end-1c")
                        self.log_text.insert("end", log_message + "\n")
                        end_pos = self.log_text.index("end-1c")
                        
                        # 各ファイルパスにタグを適用
                        for file_path in file_paths:
                            # ログメッセージ内のファイルパスの位置を検索
                            start_idx = log_message.find(file_path)
                            if start_idx != -1:
                                # 行の開始位置を計算
                                line_start = f"{start_pos.split('.')[0]}.{start_idx}"
                                line_end = f"{start_pos.split('.')[0]}.{start_idx + len(file_path)}"
                                self.log_text.tag_add("file_path", line_start, line_end)
                    else:
                        self.log_text.insert("end", log_message + "\n")
                    
                    self.log_text.see("end")
                    # ログが多すぎる場合は古いものを削除
                    lines = self.log_text.get("1.0", "end").split("\n")
                    if len(lines) > 1000:
                        self.log_text.delete("1.0", f"{len(lines) - 500}.0")
                except queue.Empty:
                    continue
                except Exception as e:
                    logger.error(f"ログ更新エラー: {e}")
        
        log_thread = threading.Thread(target=update_logs, daemon=True)
        log_thread.start()
    
    def _extract_file_paths(self, text: str) -> List[str]:
        """テキストからファイルパスを抽出"""
        file_paths = []
        # 動画ファイル拡張子
        video_extensions = r'(mp4|mkv|flv|mov|avi|webm|m4v|ts)'
        
        # Windowsパス形式 (C:\path\to\file.mp4 または C:/path/to/file.mp4)
        windows_path_pattern = rf'[A-Za-z]:[\\/](?:[^\\/:*?"<>|\r\n]+[\\/])*[^\\/:*?"<>|\r\n]+\.{video_extensions}'
        
        # Unixパス形式 (/path/to/file.mp4 または ~/path/to/file.mp4)
        unix_path_pattern = rf'(?:[/~]|\.{2}[\\/])(?:[^\\/:*?"<>|\r\n]+[\\/])*[^\\/:*?"<>|\r\n]+\.{video_extensions}'
        
        # 相対パス形式 (./recordings/file.mp4 または recordings/file.mp4)
        relative_path_pattern = rf'(?:\.{1,2}[\\/])?(?:[^\\/:*?"<>|\r\n]+[\\/])*[^\\/:*?"<>|\r\n]+\.{video_extensions}'
        
        for pattern in [windows_path_pattern, unix_path_pattern, relative_path_pattern]:
            matches = re.finditer(pattern, text, re.IGNORECASE)
            for match in matches:
                file_path = match.group(0)
                # パスが有効か確認（存在するか、または録画フォルダ内か）
                if self._is_valid_file_path(file_path):
                    file_paths.append(file_path)
        
        return list(set(file_paths))  # 重複を除去
    
    def _is_valid_file_path(self, file_path: str) -> bool:
        """ファイルパスが有効か確認"""
        try:
            # 絶対パスに変換
            if not os.path.isabs(file_path):
                # 相対パスの場合、現在のディレクトリまたは録画フォルダからのパスか確認
                abs_path = os.path.abspath(file_path)
            else:
                abs_path = file_path
            
            # ファイルが存在するか、または親ディレクトリが存在するか
            if os.path.exists(abs_path):
                return True
            
            # 録画フォルダ内のパスか確認
            try:
                if self.controller:
                    config = self.controller.config
                else:
                    import yaml
                    with open("config.yaml", "r", encoding="utf-8") as f:
                        config = yaml.safe_load(f)
                
                recording_config = config.get("recording", {})
                output_path = recording_config.get("output_path", "./recordings")
                if not os.path.isabs(output_path):
                    output_path = os.path.abspath(output_path)
                
                if abs_path.startswith(output_path):
                    return True
            except:
                pass
            
            return False
        except:
            return True  # エラーが発生した場合は有効とみなす
    
    def _on_file_path_click(self, event):
        """ファイルパスがクリックされた時の処理"""
        try:
            # クリック位置のインデックスを取得
            index = self.log_text.index(f"@{event.x},{event.y}")
            
            # タグが適用されている範囲を取得
            tags = self.log_text.tag_names(index)
            if "file_path" in tags:
                # ファイルパスを取得
                start_idx = self.log_text.index(f"{index} linestart")
                end_idx = self.log_text.index(f"{index} lineend")
                line_text = self.log_text.get(start_idx, end_idx)
                
                # ファイルパスを抽出
                file_paths = self._extract_file_paths(line_text)
                if file_paths:
                    file_path = file_paths[0]
                    self._open_file(file_path)
        except Exception as e:
            logger.error(f"ファイルパスクリックエラー: {e}")
    
    def _open_file(self, file_path: str):
        """ファイルを開く"""
        try:
            if os.path.exists(file_path):
                if platform.system() == "Windows":
                    os.startfile(file_path)
                elif platform.system() == "Darwin":  # macOS
                    subprocess.run(["open", file_path])
                else:  # Linux
                    subprocess.run(["xdg-open", file_path])
                logger.info(f"ファイルを開きました: {file_path}")
            else:
                # ファイルが見つからない場合、フォルダを開く
                folder_path = os.path.dirname(file_path)
                if os.path.exists(folder_path):
                    self._open_folder(folder_path)
                else:
                    logger.warning(f"ファイルが見つかりません: {file_path}")
        except Exception as e:
            logger.error(f"ファイルを開くエラー: {e}")
    
    def _open_folder(self, folder_path: str):
        """フォルダを開く"""
        try:
            if platform.system() == "Windows":
                os.startfile(folder_path)
            elif platform.system() == "Darwin":  # macOS
                subprocess.run(["open", folder_path])
            else:  # Linux
                subprocess.run(["xdg-open", folder_path])
        except Exception as e:
            logger.error(f"フォルダを開くエラー: {e}")
    
    def _open_recording_folder(self):
        """録画フォルダを開く"""
        try:
            if self.controller:
                config = self.controller.config
            else:
                import yaml
                with open("config.yaml", "r", encoding="utf-8") as f:
                    config = yaml.safe_load(f)
            
            recording_config = config.get("recording", {})
            output_path = recording_config.get("output_path", "./recordings")
            
            # パスを絶対パスに変換
            if not os.path.isabs(output_path):
                output_path = os.path.abspath(output_path)
            
            # フォルダが存在しない場合は作成
            if not os.path.exists(output_path):
                os.makedirs(output_path, exist_ok=True)
            
            self._open_folder(output_path)
        except Exception as e:
            logger.error(f"録画フォルダを開くエラー: {e}")
    
    def _test_obs_connection(self):
        """OBS接続をテスト"""
        def test_connection():
            try:
                if self.controller:
                    config = self.controller.config
                else:
                    import yaml
                    with open("config.yaml", "r", encoding="utf-8") as f:
                        config = yaml.safe_load(f)
                
                obs_config = config.get("obs", {})
                host = obs_config.get("host", "localhost")
                port = obs_config.get("port", 4455)
                password = obs_config.get("password", "")
                
                from obswebsocket import obsws, requests
                test_client = obsws(host, port, password)
                test_client.connect()
                
                # 接続テスト（バージョン情報を取得）
                try:
                    version = test_client.call(requests.GetVersion())
                    test_client.disconnect()
                    
                    # 成功メッセージ
                    self.root.after(0, lambda: self._show_obs_status(True, f"接続成功 (OBS {version.datain.get('obsVersion', 'Unknown')})"))
                except Exception as e:
                    test_client.disconnect()
                    raise e
                    
            except Exception as e:
                error_msg = str(e)
                self.root.after(0, lambda: self._show_obs_status(False, f"接続失敗: {error_msg}"))
        
        # 別スレッドでテスト
        test_thread = threading.Thread(target=test_connection, daemon=True)
        test_thread.start()
        self.obs_status_label.configure(text="OBS: 接続テスト中...", text_color="yellow")
    
    def _show_obs_status(self, success: bool, message: str):
        """OBS接続状態を表示"""
        if success:
            self.obs_status_label.configure(text=f"OBS: {message}", text_color="green")
        else:
            self.obs_status_label.configure(text=f"OBS: {message}", text_color="red")
        
    def _start_monitoring(self):
        """監視を開始"""
        if self.is_running:
            return
        
        try:
            self.controller = VRChatRecordingController()
            self.is_running = True
            
            # コントローラーを開始
            if not self.controller.start():
                self.is_running = False
                self.start_button.configure(state="normal")
                self.stop_button.configure(state="disabled")
                self.status_label.configure(text="● エラー（OBS接続失敗）", text_color="red")
                
                # エラーメッセージを表示
                error_dialog = ctk.CTkToplevel(self.root)
                error_dialog.title("エラー")
                error_dialog.geometry("400x150")
                ctk.CTkLabel(
                    error_dialog,
                    text="OBS Studioに接続できませんでした。\n\nOBS Studioが起動しているか、\nWebSocketサーバーが有効化されているか確認してください。",
                    justify="left"
                ).pack(padx=20, pady=20)
                ctk.CTkButton(
                    error_dialog,
                    text="OK",
                    command=error_dialog.destroy,
                    width=100
                ).pack(pady=10)
                return
            
            # UI更新
            self.start_button.configure(state="disabled")
            self.stop_button.configure(state="normal")
            self.status_label.configure(text="● 監視中", text_color="green")
            
            # 状態更新を開始
            self._start_status_updater()
            
            # OBS接続状態を更新
            self._update_obs_status()
            
            logger.info("監視を開始しました")
            
        except Exception as e:
            logger.error(f"監視開始エラー: {e}")
            self.is_running = False
            self.start_button.configure(state="normal")
            self.stop_button.configure(state="disabled")
            self.status_label.configure(text="● エラー", text_color="red")
    
    def _stop_monitoring(self):
        """監視を停止"""
        if not self.is_running:
            return
        
        self.is_running = False
        
        # コントローラーを停止
        if self.controller:
            self.controller.stop()
        
        # UI更新
        self.start_button.configure(state="normal")
        self.stop_button.configure(state="disabled")
        self.status_label.configure(text="● 停止中", text_color="gray")
        self.player_count_label.configure(text="プレイヤー数: 0")
        
        # プレイヤーリストをクリア
        self._update_players_list({})
        
        logger.info("監視を停止しました")
    
    def _start_status_updater(self):
        """状態更新を開始"""
        def update_status():
            while self.is_running and self.controller:
                try:
                    # 録画状態を更新
                    if self.controller.is_recording:
                        self.status_label.configure(text="● 録画中", text_color="red")
                    else:
                        self.status_label.configure(text="● 監視中", text_color="green")
                    
                    # プレイヤー数を更新
                    player_count = len(self.controller.current_players)
                    self.player_count_label.configure(text=f"プレイヤー数: {player_count}")
                    
                    # プレイヤーリストを更新
                    players = {}
                    for user_id, username in self.controller.current_player_names.items():
                        players[user_id] = username
                    self._update_players_list(players)
                    
                    # OBS接続状態を更新
                    self._update_obs_status()
                    
                    import time
                    time.sleep(0.5)  # 0.5秒ごとに更新
                    
                except Exception as e:
                    logger.error(f"状態更新エラー: {e}")
                    import time
                    time.sleep(1)
        
        status_thread = threading.Thread(target=update_status, daemon=True)
        status_thread.start()
    
    def _update_obs_status(self):
        """OBS接続状態を更新"""
        try:
            if self.controller and self.controller.obs_client:
                # 接続状態を確認
                try:
                    # 簡単なリクエストで接続を確認
                    self.controller.obs_client.call(requests.GetVersion())
                    self.obs_status_label.configure(text="OBS: 接続中", text_color="green")
                except:
                    self.obs_status_label.configure(text="OBS: 切断", text_color="red")
            else:
                self.obs_status_label.configure(text="OBS: 未接続", text_color="gray")
        except Exception as e:
            # エラーが発生してもログに記録するだけ
            pass
    
    def _update_players_list(self, players: Dict[str, str]):
        """プレイヤーリストを更新"""
        # 既存のウィジェットを削除
        for widget in self.player_widgets.values():
            widget.destroy()
        self.player_widgets.clear()
        
        if not players:
            self.no_players_label.pack(pady=20)
            return
        
        self.no_players_label.pack_forget()
        
        # 新しいプレイヤーウィジェットを作成
        for user_id, username in players.items():
            player_frame = ctk.CTkFrame(self.players_frame)
            player_frame.pack(fill="x", padx=5, pady=5)
            
            name_label = ctk.CTkLabel(
                player_frame,
                text=username,
                font=ctk.CTkFont(size=14, weight="bold"),
                anchor="w"
            )
            name_label.pack(side="left", padx=10, pady=5)
            
            id_label = ctk.CTkLabel(
                player_frame,
                text=user_id[:20] + "..." if len(user_id) > 20 else user_id,
                font=ctk.CTkFont(size=11),
                text_color="gray",
                anchor="w"
            )
            id_label.pack(side="left", padx=10, pady=5)
            
            self.player_widgets[user_id] = player_frame
    
    def _open_settings(self):
        """設定ウィンドウを開く"""
        settings_window = SettingsWindow(self.root, self.controller)
        settings_window.grab_set()
    
    def _open_exclude_manager(self):
        """除外ユーザー管理ウィンドウを開く"""
        exclude_window = ExcludeUserWindow(self.root, self.controller)
        exclude_window.grab_set()
    
    def run(self):
        """GUIアプリケーションを実行"""
        self.root.mainloop()


class SettingsWindow(ctk.CTkToplevel):
    """設定ウィンドウ"""
    
    def __init__(self, parent, controller: Optional[VRChatRecordingController]):
        super().__init__(parent)
        self.title("設定")
        self.geometry("500x400")
        
        self.controller = controller
        
        # 設定を読み込む
        if controller:
            self.config = controller.config
        else:
            import yaml
            try:
                with open("config.yaml", "r", encoding="utf-8") as f:
                    self.config = yaml.safe_load(f)
            except:
                self.config = {}
        
        self._create_widgets()
    
    def _create_widgets(self):
        """ウィジェットを作成"""
        main_frame = ctk.CTkScrollableFrame(self)
        main_frame.pack(fill="both", expand=True, padx=20, pady=20)
        
        # OBS設定
        obs_label = ctk.CTkLabel(main_frame, text="OBS WebSocket設定", font=ctk.CTkFont(size=16, weight="bold"))
        obs_label.pack(pady=(0, 10))
        
        obs_config = self.config.get("obs", {})
        
        ctk.CTkLabel(main_frame, text="ホスト:").pack(anchor="w", pady=(5, 0))
        self.obs_host_entry = ctk.CTkEntry(main_frame, width=300)
        self.obs_host_entry.insert(0, obs_config.get("host", "localhost"))
        self.obs_host_entry.pack(anchor="w", pady=(0, 10))
        
        ctk.CTkLabel(main_frame, text="ポート:").pack(anchor="w", pady=(5, 0))
        self.obs_port_entry = ctk.CTkEntry(main_frame, width=300)
        self.obs_port_entry.insert(0, str(obs_config.get("port", 4455)))
        self.obs_port_entry.pack(anchor="w", pady=(0, 10))
        
        ctk.CTkLabel(main_frame, text="パスワード:").pack(anchor="w", pady=(5, 0))
        self.obs_password_entry = ctk.CTkEntry(main_frame, width=300, show="*")
        self.obs_password_entry.insert(0, obs_config.get("password", ""))
        self.obs_password_entry.pack(anchor="w", pady=(0, 20))
        
        # VRChat設定
        vrchat_label = ctk.CTkLabel(main_frame, text="VRChat設定", font=ctk.CTkFont(size=16, weight="bold"))
        vrchat_label.pack(pady=(10, 10))
        
        vrchat_config = self.config.get("vrchat", {})
        
        ctk.CTkLabel(main_frame, text="ログファイルパス（空欄で自動検出）:").pack(anchor="w", pady=(5, 0))
        self.vrchat_log_entry = ctk.CTkEntry(main_frame, width=300)
        self.vrchat_log_entry.insert(0, vrchat_config.get("log_file_path", ""))
        self.vrchat_log_entry.pack(anchor="w", pady=(0, 10))
        
        # 保存ボタン
        save_button = ctk.CTkButton(
            main_frame,
            text="保存",
            command=self._save_settings,
            width=200,
            height=40
        )
        save_button.pack(pady=20)
    
    def _save_settings(self):
        """設定を保存"""
        try:
            import yaml
            
            # 設定を更新
            self.config.setdefault("obs", {})["host"] = self.obs_host_entry.get()
            self.config.setdefault("obs", {})["port"] = int(self.obs_port_entry.get())
            self.config.setdefault("obs", {})["password"] = self.obs_password_entry.get()
            
            # VRChat設定を更新
            log_path = self.vrchat_log_entry.get().strip()
            self.config.setdefault("vrchat", {})["log_file_path"] = log_path if log_path else None
            
            # ファイルに保存
            with open("config.yaml", "w", encoding="utf-8") as f:
                yaml.dump(self.config, f, allow_unicode=True, default_flow_style=False)
            
            # コントローラーがあれば再読み込み
            if self.controller:
                self.controller.config = self.controller._load_config("config.yaml")
            
            logger.info("設定を保存しました")
            
            # 成功メッセージ
            success_label = ctk.CTkLabel(
                self,
                text="設定を保存しました",
                text_color="green"
            )
            success_label.pack(pady=10)
            self.after(2000, success_label.destroy)
            
        except Exception as e:
            logger.error(f"設定保存エラー: {e}")
            error_label = ctk.CTkLabel(
                self,
                text=f"エラー: {e}",
                text_color="red"
            )
            error_label.pack(pady=10)


class ExcludeUserWindow(ctk.CTkToplevel):
    """除外ユーザー管理ウィンドウ"""
    
    def __init__(self, parent, controller: Optional[VRChatRecordingController]):
        super().__init__(parent)
        self.title("除外ユーザー管理")
        self.geometry("600x500")
        
        self.controller = controller
        
        # 設定を読み込む
        if controller:
            self.config = controller.config
            self.excluded_users = list(controller.excluded_users)
            self.excluded_user_ids = list(controller.excluded_user_ids)
        else:
            import yaml
            try:
                with open("config.yaml", "r", encoding="utf-8") as f:
                    self.config = yaml.safe_load(f)
            except:
                self.config = {}
            self.excluded_users = self.config.get("exclude", {}).get("users", [])
            self.excluded_user_ids = self.config.get("exclude", {}).get("user_ids", [])
        
        self._create_widgets()
    
    def _create_widgets(self):
        """ウィジェットを作成"""
        main_frame = ctk.CTkFrame(self)
        main_frame.pack(fill="both", expand=True, padx=20, pady=20)
        
        # ユーザー名タブ
        tabview = ctk.CTkTabview(main_frame)
        tabview.pack(fill="both", expand=True)
        
        users_tab = tabview.add("ユーザー名")
        self._create_users_tab(users_tab)
        
        ids_tab = tabview.add("ユーザーID")
        self._create_ids_tab(ids_tab)
        
        # 保存ボタン
        save_button = ctk.CTkButton(
            main_frame,
            text="保存",
            command=self._save_excludes,
            width=200,
            height=40
        )
        save_button.pack(pady=10)
    
    def _create_users_tab(self, parent):
        """ユーザー名タブを作成"""
        # 追加フレーム
        add_frame = ctk.CTkFrame(parent)
        add_frame.pack(fill="x", padx=10, pady=10)
        
        self.user_entry = ctk.CTkEntry(add_frame, placeholder_text="ユーザー名を入力")
        self.user_entry.pack(side="left", padx=5, pady=5, fill="x", expand=True)
        
        add_button = ctk.CTkButton(
            add_frame,
            text="追加",
            command=self._add_user,
            width=80
        )
        add_button.pack(side="left", padx=5, pady=5)
        
        # リストフレーム
        list_frame = ctk.CTkScrollableFrame(parent)
        list_frame.pack(fill="both", expand=True, padx=10, pady=10)
        
        self.users_list_frame = list_frame
        self.user_widgets = []
        self._update_users_list()
    
    def _create_ids_tab(self, parent):
        """ユーザーIDタブを作成"""
        # 追加フレーム
        add_frame = ctk.CTkFrame(parent)
        add_frame.pack(fill="x", padx=10, pady=10)
        
        self.id_entry = ctk.CTkEntry(add_frame, placeholder_text="ユーザーIDを入力")
        self.id_entry.pack(side="left", padx=5, pady=5, fill="x", expand=True)
        
        add_button = ctk.CTkButton(
            add_frame,
            text="追加",
            command=self._add_user_id,
            width=80
        )
        add_button.pack(side="left", padx=5, pady=5)
        
        # リストフレーム
        list_frame = ctk.CTkScrollableFrame(parent)
        list_frame.pack(fill="both", expand=True, padx=10, pady=10)
        
        self.ids_list_frame = list_frame
        self.id_widgets = []
        self._update_ids_list()
    
    def _add_user(self):
        """ユーザー名を追加"""
        username = self.user_entry.get().strip()
        if username and username not in self.excluded_users:
            self.excluded_users.append(username)
            self.user_entry.delete(0, "end")
            self._update_users_list()
    
    def _add_user_id(self):
        """ユーザーIDを追加"""
        user_id = self.id_entry.get().strip()
        if user_id and user_id not in self.excluded_user_ids:
            self.excluded_user_ids.append(user_id)
            self.id_entry.delete(0, "end")
            self._update_ids_list()
    
    def _remove_user(self, username: str):
        """ユーザー名を削除"""
        if username in self.excluded_users:
            self.excluded_users.remove(username)
            self._update_users_list()
    
    def _remove_user_id(self, user_id: str):
        """ユーザーIDを削除"""
        if user_id in self.excluded_user_ids:
            self.excluded_user_ids.remove(user_id)
            self._update_ids_list()
    
    def _update_users_list(self):
        """ユーザー名リストを更新"""
        for widget in self.user_widgets:
            widget.destroy()
        self.user_widgets.clear()
        
        for username in self.excluded_users:
            item_frame = ctk.CTkFrame(self.users_list_frame)
            item_frame.pack(fill="x", padx=5, pady=2)
            
            label = ctk.CTkLabel(item_frame, text=username, anchor="w")
            label.pack(side="left", padx=10, pady=5, fill="x", expand=True)
            
            remove_button = ctk.CTkButton(
                item_frame,
                text="削除",
                command=lambda u=username: self._remove_user(u),
                width=60,
                height=30
            )
            remove_button.pack(side="right", padx=5, pady=5)
            
            self.user_widgets.append(item_frame)
    
    def _update_ids_list(self):
        """ユーザーIDリストを更新"""
        for widget in self.id_widgets:
            widget.destroy()
        self.id_widgets.clear()
        
        for user_id in self.excluded_user_ids:
            item_frame = ctk.CTkFrame(self.ids_list_frame)
            item_frame.pack(fill="x", padx=5, pady=2)
            
            label = ctk.CTkLabel(
                item_frame,
                text=user_id[:40] + "..." if len(user_id) > 40 else user_id,
                anchor="w",
                font=ctk.CTkFont(size=11)
            )
            label.pack(side="left", padx=10, pady=5, fill="x", expand=True)
            
            remove_button = ctk.CTkButton(
                item_frame,
                text="削除",
                command=lambda u=user_id: self._remove_user_id(u),
                width=60,
                height=30
            )
            remove_button.pack(side="right", padx=5, pady=5)
            
            self.id_widgets.append(item_frame)
    
    def _save_excludes(self):
        """除外設定を保存"""
        try:
            import yaml
            
            # 空文字列を除外
            self.excluded_users = [u for u in self.excluded_users if u.strip()]
            self.excluded_user_ids = [i for i in self.excluded_user_ids if i.strip()]
            
            # 設定を更新
            self.config.setdefault("exclude", {})["users"] = self.excluded_users
            self.config.setdefault("exclude", {})["user_ids"] = self.excluded_user_ids
            
            # ファイルに保存
            with open("config.yaml", "w", encoding="utf-8") as f:
                yaml.dump(self.config, f, allow_unicode=True, default_flow_style=False)
            
            # コントローラーがあれば更新
            if self.controller:
                self.controller.excluded_users = set(self.excluded_users)
                self.controller.excluded_user_ids = set(self.excluded_user_ids)
            
            logger.info("除外設定を保存しました")
            
            # 成功メッセージ
            success_label = ctk.CTkLabel(
                self,
                text="除外設定を保存しました",
                text_color="green"
            )
            success_label.pack(pady=10)
            self.after(2000, success_label.destroy)
            
        except Exception as e:
            logger.error(f"除外設定保存エラー: {e}")
            error_label = ctk.CTkLabel(
                self,
                text=f"エラー: {e}",
                text_color="red"
            )
            error_label.pack(pady=10)


def main():
    """メイン関数"""
    app = VRChatRecordingGUI()
    app.run()


if __name__ == "__main__":
    main()

