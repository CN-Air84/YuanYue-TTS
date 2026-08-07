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
    """音乐曲目信息类。"""

    def __init__(
        self,
        song_id: str,
        name: str,
        artist: str,
        album: str,
        duration: int,
        *,
        artists=None,
        album_id=None,
        album_cover_url="",
        aliases=None,
        release_time_ms=None,
        disc_number="",
        track_number=None,
    ):
        self.song_id = str(song_id)
        self.name = str(name or "")
        self.artist = str(artist or "")
        self.album = str(album or "")
        try:
            self.duration = max(0, int(duration or 0))  # 单位：毫秒
        except (TypeError, ValueError, OverflowError):
            self.duration = 0

        self.artists = self._normalize_artists(artists, self.artist)
        if not self.artist:
            self.artist = ", ".join(self.artist_names)
        self.album_id = str(album_id) if album_id not in (None, "") else None
        self.album_cover_url = str(album_cover_url or "")
        self.aliases = self._normalize_text_list(aliases)
        self.release_time_ms = self._positive_int_or_none(release_time_ms)
        self.disc_number = str(disc_number or "")
        self.track_number = self._positive_int_or_none(track_number)
        self.url: Optional[str] = None  # 播放链接缓存
        self.lyrics: Optional[str] = None  # 歌词内容缓存
        self.parsed_lyrics: List[tuple] = [] # 解析后的歌词列表 [(ms, text), ...]

    @staticmethod
    def _normalize_artists(artists, fallback_artist: str) -> List[Dict[str, str]]:
        normalized = []
        if isinstance(artists, (list, tuple)):
            for artist in artists:
                if isinstance(artist, dict):
                    name = str(artist.get("name") or "").strip()
                    artist_id = artist.get("id")
                else:
                    name = str(artist or "").strip()
                    artist_id = None
                if not name:
                    continue
                item = {"name": name}
                if artist_id not in (None, ""):
                    item["id"] = str(artist_id)
                normalized.append(item)

        fallback_artist = str(fallback_artist or "").strip()
        if not normalized and fallback_artist:
            # Legacy queue entries only retain the combined display string. Do
            # not split on commas because a valid artist name may contain one.
            normalized.append({"name": fallback_artist})
        return normalized

    @staticmethod
    def _normalize_text_list(values) -> List[str]:
        if not isinstance(values, (list, tuple)):
            return []
        return [str(value).strip() for value in values if str(value or "").strip()]

    @staticmethod
    def _positive_int_or_none(value) -> Optional[int]:
        try:
            parsed = int(value)
        except (TypeError, ValueError, OverflowError):
            return None
        return parsed if parsed > 0 else None

    @property
    def artist_names(self) -> List[str]:
        return [artist["name"] for artist in self.artists]

    def to_dict(self) -> Dict[str, Any]:
        """Return the restart-safe queue representation."""
        return {
            "song_id": self.song_id,
            "name": self.name,
            "artist": self.artist,
            "album": self.album,
            "duration": self.duration,
            "artists": self.artists,
            "album_id": self.album_id,
            "album_cover_url": self.album_cover_url,
            "aliases": self.aliases,
            "release_time_ms": self.release_time_ms,
            "disc_number": self.disc_number,
            "track_number": self.track_number,
        }

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
                return self._select_preferred_lyrics(lyric_info)
            return None
        except AttributeError:
            debug_logger.warning("NeteaseMusicProvider", "当前pyncm版本不支持GetTrackLyrics方法，歌词功能暂时不可用")
            return None
        except Exception as e:
            debug_logger.error("NeteaseMusicProvider", f"获取歌词异常: {str(e)}")
            return None

    @staticmethod
    def _select_preferred_lyrics(lyric_info: Dict[str, Any]) -> Optional[str]:
        """按英文、日韩、中文的顺序选择一个可用歌词版本。"""
        candidates = []
        for source in ('lrc', 'tlyric'):
            lyric_data = lyric_info.get(source, {})
            if not isinstance(lyric_data, dict):
                continue
            lyrics = lyric_data.get('lyric', '')
            if isinstance(lyrics, str) and lyrics.strip():
                candidates.append(lyrics)

        if not candidates:
            return None

        language_priority = {'en': 0, 'ja_ko': 1, 'zh': 2, 'other': 3}
        return min(
            enumerate(candidates),
            key=lambda item: (
                language_priority[NeteaseMusicProvider._detect_lyrics_language(item[1])],
                item[0],
            ),
        )[1]

    @staticmethod
    def _detect_lyrics_language(lyrics: str) -> str:
        """根据歌词正文中的主要文字脚本判断语言组。"""
        body = re.sub(r'\[[^\]]*\]', '', lyrics)
        latin_count = len(re.findall(r'[A-Za-z]', body))
        kana_count = len(re.findall(r'[\u3040-\u30ff\uff66-\uff9f]', body))
        hangul_count = len(re.findall(r'[\u1100-\u11ff\u3130-\u318f\uac00-\ud7af]', body))
        cjk_count = len(re.findall(r'[\u3400-\u4dbf\u4e00-\u9fff]', body))

        scores = {
            'en': latin_count,
            'ja_ko': max(kana_count + cjk_count if kana_count else 0, hangul_count),
            'zh': cjk_count if not kana_count else 0,
        }
        language, score = max(scores.items(), key=lambda item: item[1])
        return language if score else 'other'

    def _song_to_track(self, song: Dict[str, Any]) -> MusicTrack:
        """内部转换函数"""
        raw_artists = song.get('ar') or song.get('artists') or []
        artists = []
        for artist in raw_artists:
            if not isinstance(artist, dict):
                continue
            name = str(artist.get('name') or '').strip()
            if not name:
                continue
            artists.append({"id": artist.get('id'), "name": name})

        if not artists:
            cloud_artist = str((song.get('pc') or {}).get('ar') or '').strip()
            if cloud_artist:
                artists.append({"name": cloud_artist})

        album = song.get('al') or song.get('album') or {}
        aliases = song.get('alia') or song.get('alias') or []
        return MusicTrack(
            song_id=str(song.get('id')),
            name=song.get('name'),
            artist=", ".join(artist["name"] for artist in artists),
            album=album.get('name'),
            duration=song.get('dt', song.get('duration', 0)),
            artists=artists,
            album_id=album.get('id'),
            album_cover_url=album.get('picUrl'),
            aliases=aliases,
            release_time_ms=album.get('publishTime') or song.get('publishTime'),
            disc_number=song.get('cd'),
            track_number=song.get('no'),
        )

    # ---------- 登录相关 ----------

    def is_logged_in(self) -> bool:
        """检查当前 pyncm 会话是否已登录"""
        try:
            return pyncm.GetCurrentSession().logged_in
        except Exception:
            return False

    def get_login_info(self) -> dict:
        """返回登录用户信息，未登录返回空 dict。
        返回: {"uid": int, "nickname": str, "vip_type": int}
        """
        try:
            session = pyncm.GetCurrentSession()
            if session.logged_in:
                return {
                    "uid": session.uid,
                    "nickname": session.nickname,
                    "vip_type": session.vipType,
                }
        except Exception:
            pass
        return {}

    def get_user_detail(self) -> dict:
        """获取当前登录用户的详细资料（含头像 URL）。
        返回: {"uid": int, "nickname": str, "avatar_url": str, "vip_type": int}
        未登录或失败返回空 dict。结果缓存于实例，避免重复请求。
        """
        if not self.is_logged_in():
            return {}
        # 缓存命中：若已登录且 uid 未变，直接返回缓存
        try:
            session = pyncm.GetCurrentSession()
            uid = session.uid
            cached = getattr(self, "_user_detail_cache", None)
            if cached and cached.get("uid") == uid:
                return cached
        except Exception:
            pass
        try:
            resp = pyncm.apis.user.GetUserDetail(uid)
            profile = resp.get("profile") or resp.get("user") or {}
            if not profile:
                return {}
            detail = {
                "uid": profile.get("userId") or uid,
                "nickname": profile.get("nickname") or session.nickname,
                "avatar_url": profile.get("avatarUrl", ""),
                "vip_type": profile.get("vipType", session.vipType),
            }
            self._user_detail_cache = detail
            return detail
        except Exception as e:
            debug_logger.warning("NeteaseMusicProvider", f"获取用户资料失败: {str(e)}")
            return {}

    def restore_session(self, session_dump: str) -> bool:
        """从持久化字符串恢复 pyncm 会话（启动时调用）。"""
        if not session_dump:
            return False
        try:
            session = pyncm.LoadSessionFromString(session_dump)
            pyncm.SetCurrentSession(session)
            # 验证会话是否仍然有效
            if session.logged_in:
                debug_logger.info("NeteaseMusicProvider",
                                  f"会话恢复成功，用户: {session.nickname}")
                return True
            else:
                debug_logger.warning("NeteaseMusicProvider", "会话已过期，需要重新登录。")
                return False
        except Exception as e:
            debug_logger.error("NeteaseMusicProvider",
                               f"会话恢复失败: {str(e)}")
            return False

    def dump_session(self) -> str:
        """导出当前 pyncm 会话为可持久化的字符串。"""
        try:
            return pyncm.DumpSessionAsString(pyncm.GetCurrentSession())
        except Exception as e:
            debug_logger.error("NeteaseMusicProvider",
                               f"会话导出失败: {str(e)}")
            return ""

    def logout(self):
        """登出：清除 pyncm 会话。持久化清理由调用方负责。"""
        try:
            pyncm.apis.login.LoginLogout()
            pyncm.SetNewSession()
            debug_logger.info("NeteaseMusicProvider", "已登出。")
        except Exception as e:
            debug_logger.error("NeteaseMusicProvider", f"登出异常: {str(e)}")


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
        self.current_pos = 0 # milliseconds
        self.backend_proc = None
        self._command_lock = threading.Lock()
        self._play_sequence = 0
        self.current_play_id = None
        self._last_ended_play_id = None
        self._start_backend()

    def _is_music_backend_mode(self):
        if "--music-backend" in sys.argv:
            return True
        if os.environ.get("YUANYUE_TTS_ROLE") == "music-backend":
            return True
        for arg in sys.argv[1:]:
            if os.path.basename(str(arg)).lower() == "music_backend.py":
                return True
        return False

    def _start_backend(self):
        """启动后台播放进程"""
        try:
            if self._is_music_backend_mode():
                debug_logger.info("MusicPlayer", "当前进程是音乐后台模式，跳过再次拉起后台进程")
                return

            executable_name = os.path.basename(sys.executable).lower()
            # 使用正确的路径获取方式，避免 MEI 临时目录问题
            if getattr(sys, 'frozen', False):
                script_path = os.path.join(os.path.dirname(sys.executable), "music_backend.py")
            else:
                script_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "music_backend.py")
            backend_env = None
            use_script_backend = (executable_name.startswith("python") or executable_name.startswith("pypy")) and os.path.exists(script_path)

            if use_script_backend:
                python_exe = sys.executable
                args = [python_exe, script_path]
                start_mode = "script"
            else:
                python_exe = sys.executable
                args = [python_exe, "--music-backend"]
                backend_env = os.environ.copy()
                backend_env["YUANYUE_TTS_ROLE"] = "music-backend"
                start_mode = "exe-arg"

            debug_logger.info("MusicPlayer", f"正在启动独立播放后台 (mode={start_mode}): {python_exe}")
            
            # 隐藏 cmd 窗口
            startupinfo = None
            if sys.platform == 'win32':
                startupinfo = subprocess.STARTUPINFO()
                startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                startupinfo.wShowWindow = subprocess.SW_HIDE
            
            self.backend_proc = subprocess.Popen(
                args,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1,
                env=backend_env,
                startupinfo=startupinfo
            )
            
            # 启动线程读取后台状态报告
            threading.Thread(target=self._read_backend_output, daemon=True).start()
            debug_logger.info("MusicPlayer", "独立播放后台启动成功。")
        except Exception as e:
            debug_logger.error("MusicPlayer", f"启动后台进程失败: {str(e)}")

    def _read_backend_output(self):
        """Read JSON messages from the playback backend and update local state."""
        while self.backend_proc and self.backend_proc.poll() is None:
            line = self.backend_proc.stdout.readline()
            if not line:
                break
            try:
                data = json.loads(line)
                message_type = data.get("type")

                if message_type == "status":
                    status_play_id = data.get("play_id")
                    # Ignore a delayed status message from an older playback session.
                    if status_play_id is not None and status_play_id != self.current_play_id:
                        continue
                    self.current_pos = data.get("pos", 0)
                    self.is_playing = data.get("playing", False)
                    self.is_paused = data.get("paused", False)
                elif message_type == "event" and data.get("event") == "ended":
                    self._handle_playback_ended(data.get("play_id"))
                elif message_type == "error":
                    debug_logger.error("MusicPlayer", f"Playback backend error: {data.get('msg')}")
            except Exception as e:
                debug_logger.warning("MusicPlayer", f"Ignoring invalid backend message: {str(e)}")

    def _handle_playback_ended(self, play_id):
        """Schedule auto-next once for a valid natural-end event."""
        if play_id is None or play_id != self.current_play_id:
            debug_logger.info("MusicPlayer", f"Ignoring stale playback-ended event: {play_id}")
            return
        if self._last_ended_play_id == play_id:
            debug_logger.info("MusicPlayer", f"Ignoring duplicate playback-ended event: {play_id}")
            return

        self._last_ended_play_id = play_id
        self.is_playing = False
        self.is_paused = False
        debug_logger.info("MusicPlayer", f"Playback ended; scheduling auto-next (play_id={play_id})")
        threading.Timer(0.5, self._run_auto_next, args=(play_id,)).start()

    def _run_auto_next(self, play_id):
        """Run auto-next only if the ended playback session is still current."""
        if play_id != self.current_play_id:
            debug_logger.info("MusicPlayer", f"Auto-next task is stale: {play_id}")
            return
        if self.is_playing or self.is_paused:
            debug_logger.info("MusicPlayer", f"Playback state changed; canceling auto-next: {play_id}")
            return
        self.auto_next_callback()

    def set_auto_next_callback(self, callback):
        """设置播放结束时的回调"""
        self.auto_next_callback = callback

    def auto_next_callback(self):
        """默认的回调，由外部注入逻辑"""
        pass

    def _send_cmd(self, action, **kwargs):
        """Send one JSON command to the backend without interleaving writers."""
        with self._command_lock:
            if not self.backend_proc or self.backend_proc.poll() is not None:
                debug_logger.warning("MusicPlayer", "Playback backend is closed; restarting...")
                self._start_backend()

            if not self.backend_proc or self.backend_proc.poll() is not None:
                debug_logger.error("MusicPlayer", "Playback backend is unavailable; command not sent")
                return False

            cmd = {"action": action}
            cmd.update(kwargs)
            try:
                self.backend_proc.stdin.write(json.dumps(cmd) + "\n")
                self.backend_proc.stdin.flush()
                return True
            except Exception as e:
                debug_logger.error("MusicPlayer", f"Failed to send playback command: {str(e)}")
                return False

    def play_url(self, url: str, start_ms: int = 0):
        self._play_sequence += 1
        play_id = self._play_sequence
        self.current_play_id = play_id
        self._last_ended_play_id = None
        self.current_pos = start_ms
        self.is_playing = True
        self.is_paused = False
        debug_logger.info("MusicPlayer", f"Requesting backend playback: {url[:50]}... (play_id={play_id})")
        if not self._send_cmd("play", url=url, start_ms=start_ms, play_id=play_id):
            self.is_playing = False
        return play_id

    def pause(self):
        self._send_cmd("pause")
        self.is_paused = True

    def resume(self):
        self._send_cmd("resume")
        self.is_paused = False

    def stop(self):
        # Invalidate the current session before a queued ended event can fire.
        self.current_play_id = None
        self._last_ended_play_id = None
        self.is_playing = False
        self.is_paused = False
        self.current_pos = 0
        self._send_cmd("stop")

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
        tracks = self.load_playlist_tracks(url)
        if not tracks:
            return False

        self.activate_playlist(tracks)

        debug_logger.info("MusicSubsystem", f"歌单导入成功，共 {len(tracks)} 首，开始预取前 5 首链接")

        threading.Thread(
            target=self.prefetch_tracks,
            args=(tracks, 5),
            daemon=True,
        ).start()
        return True

    def load_playlist_tracks(self, url: str) -> List[MusicTrack]:
        """解析歌单 URL 并加载歌曲，不修改当前播放列表。"""
        playlist_id = self.provider.parse_playlist_url(url)
        if not playlist_id:
            debug_logger.error("MusicSubsystem", f"无法解析歌单 URL: {url}")
            return []

        return self.provider.get_playlist_tracks(playlist_id)

    def activate_playlist(self, tracks: List[MusicTrack]):
        """把已加载的歌曲列表设为当前列表。"""
        self.current_list = tracks
        if self.play_mode == 2: self._regenerate_shuffle()

    def prefetch_tracks(self, tracks: List[MusicTrack], limit: int = 5):
        """为给定歌曲快照预取链接；调用方负责把该方法放到后台线程。"""
        snapshot = list(tracks[:max(0, limit)])
        self._prefetch_tracks_snapshot(snapshot, position_offset=0)

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
        snapshot = list(self.current_list[start:end])
        self._prefetch_tracks_snapshot(snapshot, position_offset=start)

    def _prefetch_tracks_snapshot(self, tracks: List[MusicTrack], position_offset: int):
        """预取固定歌曲快照，避免切换列表后读取到另一份 current_list。"""
        for offset, track in enumerate(tracks):
            if not track.url:
                position = position_offset + offset + 1
                debug_logger.info("MusicSubsystem", f"[预取线程] 正在获取第 {position} 首链接: {track.name}")
                url = self.provider.get_stream_url(track.song_id, self.current_quality)
                if url:
                    with self._url_fetch_lock:
                        track.url = url
        if tracks:
            start = position_offset + 1
            end = position_offset + len(tracks)
            debug_logger.info("MusicSubsystem", f"[预取线程] 范围 {start}-{end} 预取任务完成")

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
