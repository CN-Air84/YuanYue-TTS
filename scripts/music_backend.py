# coding=utf-8
import os
import sys
import threading
import time
import json
import tempfile
import requests
#来来来一人一句GLM-5牛B嗷
# 屏蔽 pygame 的欢迎信息
os.environ['PYGAME_HIDE_SUPPORT_PROMPT'] = '1'
try:
    import pygame
except ImportError:
    print(json.dumps({"type": "error", "msg": "pygame not installed"}))
    sys.exit(1)

class MusicBackend:
    def __init__(self):
        pygame.mixer.pre_init(44100, -16, 2, 1024)
        pygame.mixer.init()
        self.is_playing = False
        self.is_paused = False
        self.current_file = None
        self.start_time_offset = 0 # 毫秒
        self.volume = 1.0
        
        # 状态报告线程
        self.report_thread = threading.Thread(target=self._report_loop, daemon=True)
        self.report_thread.start()

    def _report_loop(self):
        """定期向父进程报告状态"""
        while True:
            if self.is_playing:
                pos = self.start_time_offset + pygame.mixer.music.get_pos()
                print(json.dumps({"type": "status", "pos": pos, "playing": self.is_playing, "paused": self.is_paused}), flush=True)
            time.sleep(0.5)

    def handle_command(self, cmd_json):
        try:
            data = json.loads(cmd_json)
            action = data.get("action")
            
            if action == "play":
                self._play(data.get("url"), data.get("start_ms", 0))
            elif action == "pause":
                pygame.mixer.music.pause()
                self.is_paused = True
            elif action == "resume":
                pygame.mixer.music.unpause()
                self.is_paused = False
            elif action == "stop":
                self._stop()
            elif action == "set_volume":
                self.volume = data.get("value", 1.0)
                pygame.mixer.music.set_volume(self.volume)
            elif action == "set_pos":
                pos_ms = data.get("pos_ms", 0)
                # pygame 的 set_pos 在某些格式上不可靠，最稳妥的是重新播放
                if self.current_file:
                    pygame.mixer.music.play(start=pos_ms / 1000.0)
                    self.start_time_offset = pos_ms
            elif action == "quit":
                sys.exit(0)
                
        except Exception as e:
            print(json.dumps({"type": "error", "msg": str(e)}), flush=True)

    def _play(self, url, start_ms):
        self._stop()
        
        # 下载到临时文件
        try:
            resp = requests.get(url, stream=True, timeout=15)
            resp.raise_for_status()
            
            suffix = ".flac" if "flac" in url.lower() else ".mp3"
            fd, path = tempfile.mkstemp(suffix=suffix, prefix="backend_")
            os.close(fd)
            self.current_file = path

            with open(path, 'wb') as f:
                for chunk in resp.iter_content(8192): f.write(chunk)
            
            pygame.mixer.music.load(path)
            pygame.mixer.music.set_volume(self.volume)
            pygame.mixer.music.play(start=start_ms / 1000.0)
            self.start_time_offset = start_ms
            self.is_playing = True
            self.is_paused = False
            print(json.dumps({"type": "info", "msg": f"Playing: {path}"}), flush=True)
        except Exception as e:
            print(json.dumps({"type": "error", "msg": f"Play failed: {str(e)}"}), flush=True)

    def _stop(self):
        pygame.mixer.music.stop()
        pygame.mixer.music.unload()
        if self.current_file and os.path.exists(self.current_file):
            try: os.remove(self.current_file)
            except: pass
            self.current_file = None
        self.is_playing = False
        self.is_paused = False
        self.start_time_offset = 0

if __name__ == "__main__":
    backend = MusicBackend()
    for line in sys.stdin:
        backend.handle_command(line)
