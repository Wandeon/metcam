"""
SFTP uploader for nk-otok.hr website
With bandwidth throttling and resume capability
"""

import paramiko
import os
from pathlib import Path
import time
from typing import Callable, Optional


class SFTPUploader:
    def __init__(self, host: str, username: str, password: str = None,
                 bandwidth_limit_mbps: int = 0, key_file: str = None):
        self.host = host
        self.username = username
        self.password = password
        self.key_file = key_file
        self.client = None
        self.sftp = None

        # Bandwidth throttling (0 = unlimited)
        self.bandwidth_limit_mbps = bandwidth_limit_mbps
        self.bytes_per_second = bandwidth_limit_mbps * 125000 if bandwidth_limit_mbps > 0 else 0

    def connect(self):
        """Establish SFTP connection"""
        self.client = paramiko.SSHClient()
        self.client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

        if self.key_file:
            self.client.connect(
                self.host,
                username=self.username,
                key_filename=self.key_file
            )
        else:
            self.client.connect(
                self.host,
                username=self.username,
                password=self.password
            )

        self.sftp = self.client.open_sftp()

    def upload_file(self, local_path: str, remote_path: str,
                   progress_callback: Optional[Callable] = None,
                   resume_from: int = 0):
        """
        Upload file with progress tracking, bandwidth throttling, and resume capability

        Args:
            local_path: Local file to upload
            remote_path: Remote destination path
            progress_callback: Callback(bytes_transferred, total_bytes)
            resume_from: Byte position to resume from (0 = start from beginning)
        """
        if not self.sftp:
            self.connect()

        file_size = os.path.getsize(local_path)
        start_position = resume_from

        # Check if remote file exists and get its size for resume
        if resume_from == 0:
            try:
                remote_stat = self.sftp.stat(remote_path)
                start_position = remote_stat.st_size
                print(f"Resuming upload from byte {start_position}")
            except:
                start_position = 0

        # Ensure remote directory exists
        remote_dir = os.path.dirname(remote_path)
        try:
            self.sftp.stat(remote_dir)
        except:
            self._mkdir_p(remote_dir)

        # Upload with throttling and resume
        if self.bytes_per_second > 0 or start_position > 0:
            self._upload_with_throttling(
                local_path, remote_path, file_size,
                start_position, progress_callback
            )
        else:
            # Standard upload without throttling
            def progress(transferred, total):
                if progress_callback:
                    progress_callback(transferred, total)

            self.sftp.put(local_path, remote_path, callback=progress)

        return {
            'success': True,
            'bytes_uploaded': file_size,
            'remote_path': remote_path
        }

    def _upload_with_throttling(self, local_path, remote_path, file_size,
                                start_position, progress_callback):
        """Upload with bandwidth throttling and resume support"""
        chunk_size = 32768  # 32KB chunks
        bytes_sent = start_position
        start_time = time.time()

        # Open local file
        with open(local_path, 'rb') as local_file:
            # Seek to resume position
            if start_position > 0:
                local_file.seek(start_position)

            # Open remote file (append mode if resuming)
            mode = 'ab' if start_position > 0 else 'wb'
            with self.sftp.file(remote_path, mode) as remote_file:
                while True:
                    chunk = local_file.read(chunk_size)
                    if not chunk:
                        break

                    # Write chunk
                    remote_file.write(chunk)
                    bytes_sent += len(chunk)

                    # Call progress callback
                    if progress_callback:
                        progress_callback(bytes_sent, file_size)

                    # Throttle bandwidth if limit is set
                    if self.bytes_per_second > 0:
                        elapsed = time.time() - start_time
                        expected_time = bytes_sent / self.bytes_per_second
                        if elapsed < expected_time:
                            time.sleep(expected_time - elapsed)

    def _mkdir_p(self, remote_path):
        """Create remote directory recursively"""
        dirs = []
        path = remote_path
        while path and path != '/':
            dirs.append(path)
            path = os.path.dirname(path)

        dirs.reverse()
        for dir_path in dirs:
            try:
                self.sftp.stat(dir_path)
            except:
                try:
                    self.sftp.mkdir(dir_path)
                except:
                    pass  # May already exist from concurrent operations

    def disconnect(self):
        """Close SFTP connection"""
        if self.sftp:
            self.sftp.close()
        if self.client:
            self.client.close()
