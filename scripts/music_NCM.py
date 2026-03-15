# coding=utf-8
import os
import sys
import threading
import tempfile
import requests
import re
import subprocess
import json
import time
from abc import ABC, abstractmethod
from typing import List, Dict, Optional, Any
from debug_logger import debug_logger, LogLevel

# 尝试导入 pyncm，这是网易云音乐的核心库
try:
    import pyncm
    import pyncm.apis.cloudsearch
    import pyncm.apis.track
    import pyncm.apis.playlist
    PYNCM_AVAILABLE = True
except ImportError:
    PYNCM_AVAILABLE = False
    debug_logger.warning("MusicSubsystem", "pyncm 库未安装，网易云音乐功能将不可用。")

# 尝试导入 pygame 用于音频播放
try:
    import pygame
    PYGAME_AVAILABLE = True
except ImportError:
    PYGAME_AVAILABLE = False
    debug_logger.warning("MusicSubsystem", "pygame 库未安装，音频播放功能将不可用。")


class MusicTrack:
    """音乐曲目信息类"""
    def __init__(self, song_id: str, name: str, artist: str, album: str, duration: int):
        self.song_id = song_id
        self.name = name
        self.artist = artist
        self.album = album
        self.duration = duration  # 单位：毫秒
        self.url: Optional[str] = None  # 播放链接缓存
        self.lyrics: Optional[str] = None  # 歌词内容缓存
        self.parsed_lyrics: List[tuple] = [] # 解析后的歌词列表 [(ms, text), ...]

    def __str__(self):
        return f"{self.name} - {self.artist} ({self.album})"


class BaseMusicProvider(ABC):
    """
    音乐提供商抽象基类。
    通过继承此类并实现搜索和获取流地址方法，可以轻松扩展支持其他平台。
    """
    @abstractmethod
    def search(self, keyword: str, limit: int = 5) -> List[MusicTrack]:
        """搜索音乐"""
        pass

    @abstractmethod
    def get_stream_url(self, song_id: str, quality: str = "standard") -> Optional[str]:
        """获取音乐流地址"""
        pass

    @abstractmethod
    def parse_playlist_url(self, url: str) -> Optional[str]:
        """从 URL 中解析歌单 ID"""
        pass

    @abstractmethod
    def get_playlist_tracks(self, playlist_id: str) -> List[MusicTrack]:
        """获取歌单中的所有歌曲"""
        pass

    @abstractmethod
    def get_lyrics(self, song_id: str) -> Optional[str]:
        """获取歌词"""
        pass


class NeteaseMusicProvider(BaseMusicProvider):
    """
    网易云音乐提供商实现。
    使用 pyncm 库与网易云 API 交互。
    """
    def __init__(self):
        if not PYNCM_AVAILABLE:
            raise RuntimeError("pyncm 库不可用，无法使用网易云音乐提供商。")
        debug_logger.info("NeteaseMusicProvider", "网易云音乐提供商已初始化。")

    def search(self, keyword: str, limit: int = 30, offset: int = 0) -> List[MusicTrack]:
        """网易云搜索，支持分页"""
        try:
            debug_logger.info("NeteaseMusicProvider", f"正在搜索: {keyword}, 偏移量: {offset}")
            results = pyncm.apis.cloudsearch.GetSearchResult(keyword, stype=1, limit=limit, offset=offset)
            tracks = []
            if results.get('code') == 200:
                song_list = results.get('result', {}).get('songs', [])
                for song in song_list:
                    tracks.append(self._song_to_track(song))
            return tracks
        except Exception as e:
            debug_logger.error("NeteaseMusicProvider", f"搜索异常: {str(e)}")
            return []

    def get_stream_url(self, song_id: str, quality: str = "standard") -> Optional[str]:
        """获取播放链接"""
        try:
            bitrates = {"standard": 128000, "higher": 192000, "exhigh": 320000, "lossless": 999000, "hires": 999001}
            bitrate = bitrates.get(quality, 128000)
            audio_info = pyncm.apis.track.GetTrackAudio(song_id, bitrate=bitrate)
            if audio_info.get('code') == 200:
                data = audio_info.get('data', [])
                if data and data[0].get('url'):
                    return data[0].get('url')
            return None
        except Exception as e:
            debug_logger.error("NeteaseMusicProvider", f"获取流链接异常: {str(e)}")
            return None

    def parse_playlist_url(self, url: str) -> Optional[str]:
        """解析网易云歌单 URL 中的 ID"""
        # 匹配 id=123456 或 playlist/123456
        match = re.search(r'id=(\d+)', url) or re.search(r'playlist/(\d+)', url)
        return match.group(1) if match else None

    def get_playlist_tracks(self, playlist_id: str) -> List[MusicTrack]:
        """获取歌单歌曲列表"""
        try:
            debug_logger.info("NeteaseMusicProvider", f"正在获取歌单 ID: {playlist_id} 的歌曲列表")
            res = pyncm.apis.playlist.GetPlaylistInfo(playlist_id)
            tracks = []
            if res.get('code') == 200:
                playlist = res.get('playlist', {})
                # 注意：GetPlaylistInfo 可能只返回部分歌曲 ID，需要进一步获取详情
                track_ids = [t.get('id') for t in playlist.get('trackIds', [])]
                if track_ids:
                    # 分批获取歌曲详情 (pyncm 内部处理)
                    track_details = pyncm.apis.track.GetTrackDetail(track_ids)
                    if track_details.get('code') == 200:
                        for song in track_details.get('songs', []):
                            tracks.append(self._song_to_track(song))
            debug_logger.info("NeteaseMusicProvider", f"成功获取歌单歌曲，共 {len(tracks)} 首")
            return tracks
        except Exception as e:
            debug_logger.error("NeteaseMusicProvider", f"获取歌单歌曲异常: {str(e)}")
            return []

    def get_lyrics(self, song_id: str) -> Optional[str]:
        """获取网易云歌词"""
        try:
            debug_logger.info("NeteaseMusicProvider", f"正在获取歌词: {song_id}")
            lyric_info = pyncm.apis.track.GetTrackLyrics(song_id)
            if lyric_info.get('code') == 200:
                lrc = lyric_info.get('lrc', {}).get('lyric', '')
                tlyric = lyric_info.get('tlyric', {}).get('lyric', '')
                if tlyric:
                    return f"{lrc}\n{tlyric}"
                return lrc
            return None
        except AttributeError:
            debug_logger.warning("NeteaseMusicProvider", "当前pyncm版本不支持GetTrackLyrics方法，歌词功能暂时不可用")
            return None
        except Exception as e:
            debug_logger.error("NeteaseMusicProvider", f"获取歌词异常: {str(e)}")
            return None

    def _song_to_track(self, song: Dict[str, Any]) -> MusicTrack:
        """内部转换函数"""
        return MusicTrack(
            song_id=str(song.get('id')),
            name=song.get('name'),
            artist=", ".join([ar.get('name') for ar in song.get('ar', [])]),
            album=song.get('al', {}).get('name'),
            duration=song.get('dt', 0)
        )


class MusicPlayer:
    """
    重构后的播放器核心。
    通过启动一个独立的 Python 后台进程来播放音频。
    这实现了“独立流媒体播放线程”，使其与主进程的音频播放（如听写预览）完全隔离。
    两者现在可以同时出声而不会互相中断。
    """
    def __init__(self):
        self.is_playing = False
        self.is_paused = False
        self.volume = 1.0
        self.current_pos = 0 # 毫秒
        self.backend_proc = None
        self._start_backend()

    def _start_backend(self):
        """启动后台播放进程"""
        try:
            # 判断是否处于打包状态
            is_frozen = getattr(sys, 'frozen', False)
            
            if is_frozen:
                # 打包环境下，sys.executable 就是主程序 EXE
                # 我们通过传递特殊命令行参数来让主程序启动进入后台模式
                python_exe = sys.executable
                args = [python_exe, "--music-backend"]
            else:
                # 开发环境下，寻找 python.exe
                python_exe = os.path.join(os.path.dirname(sys.executable), "python.exe")
                if not os.path.exists(python_exe):
                    python_exe = sys.executable
                
                script_path = os.path.join(os.path.dirname(__file__), "music_backend.py")
                args = [python_exe, script_path]
            
            debug_logger.info("MusicPlayer", f"正在启动独立播放后台 (Frozen={is_frozen}): {python_exe}")
            self.backend_proc = subprocess.Popen(
                args,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1
            )
            
            # 启动线程读取后台状态报告
            threading.Thread(target=self._read_backend_output, daemon=True).start()
            debug_logger.info("MusicPlayer", "独立播放后台启动成功。")
        except Exception as e:
            debug_logger.error("MusicPlayer", f"启动后台进程失败: {str(e)}")

    def _read_backend_output(self):
        """持续读取后台进程的 stdout 输出并更新状态"""
        while self.backend_proc and self.backend_proc.poll() is None:
            line = self.backend_proc.stdout.readline()
            if not line: break
            try:
                data = json.loads(line)
                if data.get("type") == "status":
                    old_playing = self.is_playing
                    self.current_pos = data.get("pos", 0)
                    self.is_playing = data.get("playing", False)
                    self.is_paused = data.get("paused", False)
                    
                    # 自动连播逻辑：如果之前在播，现在停了，且不是人为暂停
                    if old_playing and not self.is_playing and not self.is_paused:
                        debug_logger.info("MusicPlayer", "检测到歌曲播放结束，准备自动切换下一首")
                        # 延迟一小会儿触发，防止进程竞争
                        threading.Timer(0.5, self.auto_next_callback).start()
                elif data.get("type") == "error":
                    debug_logger.error("MusicPlayer", f"后台错误: {data.get('msg')}")
            except: pass

    def set_auto_next_callback(self, callback):
        """设置播放结束时的回调"""
        self.auto_next_callback = callback

    def auto_next_callback(self):
        """默认的回调，由外部注入逻辑"""
        pass

    def _send_cmd(self, action, **kwargs):
        """向后台进程发送指令"""
        if not self.backend_proc or self.backend_proc.poll() is not None:
            debug_logger.warning("MusicPlayer", "后台进程已关闭，尝试重新启动...")
            self._start_backend()
            
        cmd = {"action": action}
        cmd.update(kwargs)
        try:
            self.backend_proc.stdin.write(json.dumps(cmd) + "\n")
            self.backend_proc.stdin.flush()
        except Exception as e:
            debug_logger.error("MusicPlayer", f"发送指令失败: {str(e)}")

    def play_url(self, url: str, start_ms: int = 0):
        debug_logger.info("MusicPlayer", f"请求独立线程播放: {url[:50]}...")
        self._send_cmd("play", url=url, start_ms=start_ms)
        self.is_playing = True
        self.is_paused = False

    def pause(self):
        self._send_cmd("pause")
        self.is_paused = True

    def resume(self):
        self._send_cmd("resume")
        self.is_paused = False

    def stop(self):
        self._send_cmd("stop")
        self.is_playing = False
        self.is_paused = False
        self.current_pos = 0

    def set_volume(self, val: float):
        self.volume = val
        self._send_cmd("set_volume", value=val)

    def get_pos(self) -> int:
        """从后台报告的状态中获取位置"""
        return self.current_pos

    def set_pos(self, pos_ms: int):
        """请求后台跳转位置"""
        self._send_cmd("set_pos", pos_ms=pos_ms)
        self.current_pos = pos_ms

    def __del__(self):
        """销毁时退出后台进程"""
        if self.backend_proc:
            try:
                self._send_cmd("quit")
                self.backend_proc.terminate()
            except: pass


import random

class MusicSubsystem:
    """音乐子系统门面"""
    def __init__(self):
        self.provider: BaseMusicProvider = NeteaseMusicProvider()
        self.player = MusicPlayer()
        self.current_list: List[MusicTrack] = []
        self.current_track: Optional[MusicTrack] = None
        self.current_index: int = -1 # 0-based
        self.current_quality = "standard"
        
        # 播放模式：0-列表循环, 1-单曲循环, 2-随机播放
        self.play_mode = 0
        self.player.set_auto_next_callback(self.next_song)
        
        # 随机播放增强逻辑：预生成随机序列
        self.shuffled_indices = []
        self.shuffled_ptr = -1 # 当前在随机序列中的位置
        
        self._url_fetch_lock = threading.Lock() # 用于线程安全的 URL 缓存更新
        debug_logger.info("MusicSubsystem", "音乐子系统已就绪")

    def _parse_lrc(self, lrc_content: str) -> List[tuple]:
        """解析 LRC 格式歌词，返回 (ms, text) 列表"""
        lyrics = []
        if not lrc_content:
            return lyrics

        # 匹配 [mm:ss.xx] 或 [mm:ss:xx] 或 [mm:ss]
        # 支持一行多个时间戳的情况：[00:12.34][00:15.67]Text
        pattern = re.compile(r'\[(\d+):(\d+)(?:\.|:)?(\d+)?\]')
        
        for line in lrc_content.split('\n'):
            line = line.strip()
            if not line: continue
            
            # 提取所有时间戳
            matches = list(pattern.finditer(line))
            if not matches: continue
            
            # 最后一个时间戳之后的内容即为文本
            last_match = matches[-1]
            text = line[last_match.end():].strip()
            
            for match in matches:
                m, s, ms = match.groups()
                # ms 可能不存在 (对应 [mm:ss])
                ms_val = int(ms) if ms else 0
                # 网易云的 ms 可能是 2 位或 3 位
                if ms and len(ms) == 2:
                    ms_val *= 10
                
                total_ms = int(m) * 60000 + int(s) * 1000 + ms_val
                lyrics.append((total_ms, text))
        
        # 按时间排序
        lyrics.sort(key=lambda x: x[0])
        return lyrics

    def set_play_mode(self, mode: int):
        """设置播放模式并根据需要初始化随机序列"""
        self.play_mode = mode
        if mode == 2: # 随机播放
            self._regenerate_shuffle()
        else:
            # 切换回顺序模式时，清空随机索引
            self.shuffled_indices = []
            self.shuffled_ptr = -1

    def _regenerate_shuffle(self, exclude_current=False):
        """
        生成一个新的随机播放序列。
        exclude_current: 如果为 True，则确保第一首歌不是当前正在播放的。
        """
        if not self.current_list:
            self.shuffled_indices = []
            self.shuffled_ptr = -1
            return
            
        count = len(self.current_list)
        self.shuffled_indices = list(range(count))
        random.shuffle(self.shuffled_indices)
        
        if 0 <= self.current_index < count:
            if not exclude_current:
                # 把当前正在播放的歌曲移到随机序列的第一位
                try:
                    self.shuffled_indices.remove(self.current_index)
                    self.shuffled_indices.insert(0, self.current_index)
                    self.shuffled_ptr = 0
                except ValueError:
                    self.shuffled_ptr = -1
            else:
                # 确保第一首歌不是当前这首（通常用于播放完毕后的二次打乱）
                if self.shuffled_indices[0] == self.current_index and count > 1:
                    # 随便跟后面一个换一下
                    self.shuffled_indices[0], self.shuffled_indices[1] = self.shuffled_indices[1], self.shuffled_indices[0]
                self.shuffled_ptr = -1
        else:
            self.shuffled_ptr = -1

    def search(self, keyword: str, offset: int = 0) -> List[MusicTrack]:
        """搜索并设为当前列表 (支持分页)"""
        results = self.provider.search(keyword, limit=30, offset=offset)
        if offset == 0:
            self.current_list = results
            if self.play_mode == 2: self._regenerate_shuffle()
        else:
            old_count = len(self.current_list)
            self.current_list.extend(results)
            if self.play_mode == 2: self._regenerate_shuffle() # 列表变动，重新随机
        return results

    def import_playlist(self, url: str) -> bool:
        """
        导入歌单。
        导入时自动开启线程获取前 5 首歌曲的播放链接。
        """
        playlist_id = self.provider.parse_playlist_url(url)
        if not playlist_id:
            debug_logger.error("MusicSubsystem", f"无法解析歌单 URL: {url}")
            return False
        
        tracks = self.provider.get_playlist_tracks(playlist_id)
        if not tracks:
            return False
            
        self.current_list = tracks
        if self.play_mode == 2: self._regenerate_shuffle()
        
        debug_logger.info("MusicSubsystem", f"歌单导入成功，共 {len(tracks)} 首，开始预取前 5 首链接")
        
        # 线程隔离：后台获取前 5 首链接
        threading.Thread(target=self._prefetch_range, args=(0, 5), daemon=True).start()
        return True

    def remove_track_by_index(self, index: int):
        """
        从当前列表中移除歌曲 (1-based)。
        """
        if not self.current_list or not (1 <= index <= len(self.current_list)):
            return
            
        idx = index - 1
        removed_track = self.current_list.pop(idx)
        debug_logger.info("MusicSubsystem", f"已从当前列表移除: {removed_track.name}")
        
        # 更新当前播放索引
        if idx == self.current_index:
            # 如果删除的是正在播放的，停止播放
            self.stop()
            self.current_index = -1
            self.current_track = None
        elif idx < self.current_index:
            # 如果删除的是当前播放之前的，索引减 1
            self.current_index -= 1
            
        # 如果是随机模式，重新生成随机序列
        if self.play_mode == 2:
            self._regenerate_shuffle()
        elif self.shuffled_indices:
            # 即使不是随机模式，如果存过序列也清空
            self.shuffled_indices = []
            self.shuffled_ptr = -1

    def play_by_index(self, index: int):
        """
        根据序号播放 (1-based)。
        """
        if not self.current_list or not (1 <= index <= len(self.current_list)):
            debug_logger.warning("MusicSubsystem", f"无效播放序号: {index}")
            return

        self.current_index = index - 1
        
        # 如果是随机模式，更新指针位置
        if self.play_mode == 2 and self.shuffled_indices:
            try:
                self.shuffled_ptr = self.shuffled_indices.index(self.current_index)
            except ValueError:
                # 如果没在序列里（例如列表刚变动），重新生成并定位
                self._regenerate_shuffle()

        track = self.current_list[self.current_index]
        self.current_track = track
        debug_logger.info("MusicSubsystem", f"准备播放序号 {index}: {track}")

        # 触发预取逻辑：如果播放的是第 n 首且 n > 4 (index > 4)
        # 获取第 n+1 到 n+5 首 (即 index 到 index + 5 范围)
        if index > 4:
            threading.Thread(target=self._prefetch_range, args=(index, index + 5), daemon=True).start()

        # 获取当前歌曲链接
        url = self._get_or_fetch_url(track)
        if url:
            self.player.play_url(url)
        else:
            debug_logger.error("MusicSubsystem", f"无法播放 {track.name}，未找到有效链接")

    def _get_or_fetch_url(self, track: MusicTrack) -> Optional[str]:
        """获取缓存链接，若无则实时获取 (线程安全)"""
        if track.url:
            return track.url
        
        # 如果缓存中没有，实时获取
        url = self.provider.get_stream_url(track.song_id, self.current_quality)
        if url:
            with self._url_fetch_lock:
                track.url = url
        return url

    def _prefetch_range(self, start: int, end: int):
        """
        后台预取指定范围的歌曲链接。
        start, end 为 0-based 索引。
        """
        end = min(end, len(self.current_list))
        for i in range(start, end):
            track = self.current_list[i]
            if not track.url:
                debug_logger.info("MusicSubsystem", f"[预取线程] 正在获取第 {i+1} 首链接: {track.name}")
                url = self.provider.get_stream_url(track.song_id, self.current_quality)
                if url:
                    with self._url_fetch_lock:
                        track.url = url
        debug_logger.info("MusicSubsystem", f"[预取线程] 范围 {start+1}-{end} 预取任务完成")

    def set_quality(self, q: str): self.current_quality = q
    def set_volume(self, v: float): self.player.set_volume(v)
    def pause(self): self.player.pause()
    def resume(self): self.player.resume()
    def stop(self): self.player.stop()

    def get_current_lyrics(self) -> Optional[str]:
        """获取当前播放歌曲的歌词"""
        if not self.current_track:
            return None
        
        if self.current_track.lyrics:
            return self.current_track.lyrics
            
        # 实时获取并缓存
        lyrics = self.provider.get_lyrics(self.current_track.song_id)
        if lyrics:
            self.current_track.lyrics = lyrics
            self.current_track.parsed_lyrics = self._parse_lrc(lyrics)
        return lyrics

    def play_all(self):
        """一键播放逻辑：根据当前模式从头开始播放"""
        if not self.current_list:
            return
            
        if self.play_mode == 2: # 随机模式
            # 重新生成一个随机序列，不一定要求保持当前歌曲在首位，因为是“点了一键播放”
            self._regenerate_shuffle(exclude_current=False)
            if self.shuffled_indices:
                self.shuffled_ptr = 0
                idx = self.shuffled_indices[0]
                self.play_by_index(idx + 1)
        else: # 顺序/列表循环/单曲循环 (一键播放通常指从第一首开始顺序播放)
            self.play_by_index(1)

    def next_song(self):
        """播放下一曲 (根据播放模式)"""
        if not self.current_list: return
        
        count = len(self.current_list)
        if self.play_mode == 0: # 列表循环
            idx = (self.current_index + 1) % count
        elif self.play_mode == 1: # 单曲循环
            idx = self.current_index
        else: # 随机播放 (预生成序列模式)
            if not self.shuffled_indices or len(self.shuffled_indices) != count:
                self._regenerate_shuffle()
            
            if not self.shuffled_indices: return
            
            self.shuffled_ptr += 1
            if self.shuffled_ptr >= len(self.shuffled_indices):
                # 隐藏歌单播放完毕，再次打乱
                debug_logger.info("MusicSubsystem", "随机序列播放完毕，重新打乱")
                self._regenerate_shuffle(exclude_current=True)
                self.shuffled_ptr = 0
                
            idx = self.shuffled_indices[self.shuffled_ptr]
            
        self.play_by_index(idx + 1)

    def prev_song(self):
        """播放上一曲"""
        if not self.current_list: return
        
        count = len(self.current_list)
        if self.play_mode == 2 and self.shuffled_indices:
            # 随机模式下，沿随机序列后退
            self.shuffled_ptr = (self.shuffled_ptr - 1) % len(self.shuffled_indices)
            idx = self.shuffled_indices[self.shuffled_ptr]
        else:
            # 顺序/循环模式
            idx = (self.current_index - 1) % count
            
        self.play_by_index(idx + 1)


if __name__ == "__main__":
    # 测试代码
    sub = MusicSubsystem()
    # sub.import_playlist("https://music.163.com/#/playlist?id=12345678")
    # sub.play_by_index(1)
