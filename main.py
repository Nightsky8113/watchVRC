#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
V睡録画ソフト - メインプログラム
VRChatのV睡中に参加してきた人の活動を自動録画します
"""

import asyncio
import logging
import os
import sys
import threading
from datetime import datetime
from pathlib import Path
from typing import Set, Optional

import yaml
from obswebsocket import obsws, requests
from pythonosc import dispatcher
from pythonosc import osc_server

from vrchat_log_monitor import VRChatLogMonitor

# ログ設定
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('vrchat_recording.log', encoding='utf-8'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)


class VRChatRecordingController:
    """VRChat録画コントローラー"""
    
    def __init__(self, config_path: str = "config.yaml"):
        """初期化"""
        self.config = self._load_config(config_path)
        self.obs_client = None
        self.is_recording = False
        self.current_players: Set[str] = set()  # 現在のプレイヤーIDセット
        self.current_player_names: dict[str, str] = {}  # user_id -> username のマッピング
        self.excluded_users = set(self.config.get('exclude', {}).get('users', []))
        self.excluded_user_ids = set(self.config.get('exclude', {}).get('user_ids', []))
        self.log_monitor: Optional[VRChatLogMonitor] = None
        self.monitor_thread: Optional[threading.Thread] = None
        
        # ログレベル設定
        log_level = self.config.get('logging', {}).get('level', 'INFO')
        logging.getLogger().setLevel(getattr(logging, log_level))
        
        logger.info("V睡録画ソフトを起動しました")
        logger.info(f"除外ユーザー: {self.excluded_users}")
        logger.info(f"除外ユーザーID: {self.excluded_user_ids}")
    
    def _load_config(self, config_path: str) -> dict:
        """設定ファイルを読み込む"""
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f)
            logger.info(f"設定ファイルを読み込みました: {config_path}")
            return config
        except FileNotFoundError:
            logger.error(f"設定ファイルが見つかりません: {config_path}")
            sys.exit(1)
        except yaml.YAMLError as e:
            logger.error(f"設定ファイルの読み込みエラー: {e}")
            sys.exit(1)
    
    def _connect_obs(self) -> bool:
        """OBS WebSocketに接続"""
        try:
            obs_config = self.config.get('obs', {})
            host = obs_config.get('host', 'localhost')
            port = obs_config.get('port', 4455)
            password = obs_config.get('password', '')
            
            self.obs_client = obsws(host, port, password)
            self.obs_client.connect()
            logger.info(f"OBS WebSocketに接続しました: {host}:{port}")
            return True
        except Exception as e:
            logger.error(f"OBS WebSocket接続エラー: {e}")
            logger.error("OBS Studioが起動しているか、WebSocketサーバーが有効化されているか確認してください")
            return False
    
    def _disconnect_obs(self):
        """OBS WebSocketから切断"""
        if self.obs_client:
            try:
                self.obs_client.disconnect()
                logger.info("OBS WebSocketから切断しました")
            except Exception as e:
                logger.error(f"OBS切断エラー: {e}")
    
    def _start_recording(self):
        """録画を開始"""
        if self.is_recording:
            logger.warning("既に録画中です")
            return
        
        try:
            # 録画開始
            self.obs_client.call(requests.StartRecording())
            self.is_recording = True
            
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            logger.info(f"録画を開始しました - {timestamp}")
            
            # 録画ファイルのパスを取得してログに出力
            try:
                output_settings = self.obs_client.call(requests.GetRecordingSettings())
                if output_settings and hasattr(output_settings, 'datain'):
                    recording_path = output_settings.datain.get('recordingPath', '')
                    if recording_path:
                        logger.info(f"録画ファイル: {recording_path}")
            except:
                pass  # 録画パスの取得に失敗しても続行
                
        except Exception as e:
            logger.error(f"録画開始エラー: {e}")
            self.is_recording = False
    
    def _stop_recording(self):
        """録画を停止"""
        if not self.is_recording:
            logger.warning("録画中ではありません")
            return
        
        try:
            # 録画停止
            self.obs_client.call(requests.StopRecording())
            self.is_recording = False
            
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            logger.info(f"録画を停止しました - {timestamp}")
            
            # 録画ファイルのパスを取得してログに出力
            try:
                output_settings = self.obs_client.call(requests.GetRecordingSettings())
                if output_settings and hasattr(output_settings, 'datain'):
                    recording_path = output_settings.datain.get('recordingPath', '')
                    if recording_path:
                        logger.info(f"録画ファイル: {recording_path}")
            except:
                pass  # 録画パスの取得に失敗しても続行
                
        except Exception as e:
            logger.error(f"録画停止エラー: {e}")
    
    def _is_excluded(self, username: str = None, user_id: str = None) -> bool:
        """ユーザーが除外対象かどうかを判定"""
        if username:
            # ユーザー名の部分一致もチェック（大文字小文字を無視）
            username_lower = username.lower()
            for excluded in self.excluded_users:
                if excluded and excluded.lower() in username_lower:
                    return True
        
        if user_id and user_id in self.excluded_user_ids:
            return True
        return False
    
    def _handle_player_joined(self, username: str, user_id: str):
        """プレイヤーが参加した時の処理（ログ監視から呼ばれる）"""
        # 除外チェック
        if self._is_excluded(username=username, user_id=user_id):
            logger.info(f"除外ユーザーが参加しました（カウント外）: {username} ({user_id})")
            return
        
        if user_id not in self.current_players:
            self.current_players.add(user_id)
            self.current_player_names[user_id] = username
            logger.info(f"プレイヤーが参加しました: {username} ({user_id}) [現在の人数: {len(self.current_players)}]")
            
            # 最初の参加者で録画開始
            if len(self.current_players) == 1 and not self.is_recording:
                self._start_recording()
    
    def _handle_player_left(self, username: str, user_id: str):
        """プレイヤーが退出した時の処理（ログ監視から呼ばれる）"""
        # 除外チェック
        if self._is_excluded(username=username, user_id=user_id):
            logger.info(f"除外ユーザーが退出しました（カウント外）: {username} ({user_id})")
            return
        
        if user_id in self.current_players:
            self.current_players.remove(user_id)
            self.current_player_names.pop(user_id, None)
            logger.info(f"プレイヤーが退出しました: {username} ({user_id}) [現在の人数: {len(self.current_players)}]")
            
            # 全員退出で録画停止
            if len(self.current_players) == 0 and self.is_recording:
                self._stop_recording()
    
    def _on_player_joined_osc(self, address: str, *args):
        """プレイヤーが参加した時の処理（OSCから呼ばれる）"""
        logger.debug(f"OSCプレイヤー参加イベント受信: {address} - {args}")
        
        # OSCメッセージからユーザー情報を取得
        # VRChatのOSCメッセージ形式に応じて調整が必要
        # ここでは簡易的な実装
        if len(args) >= 2:
            username = str(args[0])
            user_id = str(args[1])
            self._handle_player_joined(username, user_id)
        elif len(args) > 0:
            user_id = str(args[0])
            self._handle_player_joined("", user_id)
    
    def _on_player_left_osc(self, address: str, *args):
        """プレイヤーが退出した時の処理（OSCから呼ばれる）"""
        logger.debug(f"OSCプレイヤー退出イベント受信: {address} - {args}")
        
        if len(args) >= 2:
            username = str(args[0])
            user_id = str(args[1])
            self._handle_player_left(username, user_id)
        elif len(args) > 0:
            user_id = str(args[0])
            self._handle_player_left("", user_id)
    
    def _setup_osc_dispatcher(self):
        """OSCディスパッチャーを設定"""
        disp = dispatcher.Dispatcher()
        
        # VRChatのOSCメッセージを設定
        # 実際のVRChat OSCメッセージ形式に応じて調整が必要
        disp.map("/vrc/player/joined", self._on_player_joined_osc)
        disp.map("/vrc/player/left", self._on_player_left_osc)
        
        return disp
    
    def _start_log_monitoring(self):
        """ログファイル監視を開始"""
        vrchat_config = self.config.get('vrchat', {})
        log_file_path = vrchat_config.get('log_file_path')
        
        self.log_monitor = VRChatLogMonitor(log_file_path)
        self.log_monitor.set_callbacks(
            on_joined=self._handle_player_joined,
            on_left=self._handle_player_left
        )
        
        # 別スレッドで監視を開始
        def monitor_loop():
            if self.log_monitor.log_file_path:
                while True:
                    self.log_monitor.check_new_logs()
                    import time
                    time.sleep(0.5)  # 0.5秒ごとにチェック
        
        self.monitor_thread = threading.Thread(target=monitor_loop, daemon=True)
        self.monitor_thread.start()
        logger.info("VRChatログファイルの監視を開始しました")
    
    def start(self):
        """監視を開始（非ブロッキング）"""
        # OBSに接続
        if not self._connect_obs():
            logger.error("OBSに接続できませんでした。")
            return False
        
        try:
            # ログファイル監視を開始（推奨方法）
            self._start_log_monitoring()
            
            # OSCサーバーも起動（オプション、ログ監視と併用可能）
            vrchat_config = self.config.get('vrchat', {})
            use_osc = vrchat_config.get('use_osc', False)
            
            if use_osc:
                osc_port = vrchat_config.get('osc_port', 9000)
                disp = self._setup_osc_dispatcher()
                self.osc_server = osc_server.ThreadingOSCUDPServer(
                    ("127.0.0.1", osc_port), disp
                )
                # OSCサーバーを別スレッドで起動
                osc_thread = threading.Thread(target=self.osc_server.serve_forever, daemon=True)
                osc_thread.start()
                logger.info(f"OSCサーバーを起動しました: 127.0.0.1:{osc_port}")
            
            logger.info("VRChatのプレイヤー出入りを監視中...")
            return True
            
        except Exception as e:
            logger.error(f"エラーが発生しました: {e}")
            return False
    
    def stop(self):
        """監視を停止"""
        # 録画中なら停止
        if self.is_recording:
            self._stop_recording()
        
        # OSCサーバーを停止
        if hasattr(self, 'osc_server'):
            try:
                self.osc_server.shutdown()
            except:
                pass
        
        self._disconnect_obs()
        logger.info("監視を停止しました")
    
    def run(self):
        """メインループを実行（コマンドライン用、ブロッキング）"""
        if not self.start():
            return
        
        try:
            # メインスレッドで待機
            while True:
                import time
                time.sleep(1)
        except KeyboardInterrupt:
            logger.info("終了シグナルを受信しました")
        except Exception as e:
            logger.error(f"エラーが発生しました: {e}")
        finally:
            self.stop()


def main():
    """メイン関数"""
    controller = VRChatRecordingController()
    controller.run()


if __name__ == "__main__":
    main()

