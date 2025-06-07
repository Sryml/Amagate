# Author: Sryml
# Email: sryml@hotmail.com
# Python Version: 1.5
# License: MIT

import Bladex

#
import threading
import sys
import string
import select
import time
import struct
import os

sys.path.append("../../LIB/PythonLib/Plat-Win")

import socket

#
import BODLoader

#
from AmagateClient.Scripts import utils

############################
true = 1 == 1
false = not true

client_thread = None

KEY = "AmagateClient"

SERVER_HOST = "127.0.0.1"
SERVER_PORT = 1673

HEARTBEAT_INTERVAL = 3  # 5  # 心跳间隔(秒)
HEARTBEAT_TIMEOUT = 6  # 10  # 心跳超时(秒)
############################

printx = utils.printx
log_file = "../../bin/AmagateClient.log"

logger = utils.SimpleLogger("Amagate", level="DEBUG", output=open(log_file, "a"))
############################


# def recv_exact(sock, length):
#     """阻塞读取指定长度的数据，直到收完或连接关闭"""
#     data = bytearray()
#     while len(data) < length:
#         remaining = length - len(data)
#         chunk = sock.recv(remaining)
#         if not chunk:  # 连接被对方关闭
#             raise ConnectionError(f"Connection closed, expected {length} bytes, got {len(data)}")
#         data.extend(chunk)
#     return bytes(data)


class ClientThread(threading.Thread):
    def __init__(self, *args):
        # threading.Thread.__init__(self, *args)
        apply(threading.Thread.__init__, (self,) + args)
        self.name = "Amagate Client Thread"
        self.sock = None  # type: socket.socket | None
        self.last_heartbeat = time.time()
        self.sock_lock = threading.Lock()
        self.sock_lock.acquire()
        self.callback = None
        self.callback_args = ()
        #
        # self.log_file = open("../../bin/AmagateClient.log","w")

    def handle_message(self):
        # print不是线程安全的，会导致游戏崩溃
        sock = self.sock
        while 1:
            # 如果客户端被卸载，则退出循环
            if not BODLoader.BLModInfo["Amagate Client"]["Installed"]:
                logger.debug("Client uninstalled")
                break
            # 如果客户端被禁用，则退出循环
            if not BODLoader.BLModInfo["Amagate Client"]["Enabled"]:
                logger.debug("Client disabled")
                break
            # 如果锁被释放，则退出循环
            if not self.sock_lock.locked():
                logger.debug("Socket lock released")
                break

            readable, writable, exceptional = select.select([sock], [sock], [sock], 2.0)
            if readable:
                msg = sock.recv(2)
                if not msg:  # 服务器关闭连接
                    logger.debug("Server closed connection")
                    break

                msg_type = struct.unpack("!H", msg)[0]
                logger.debug("msg_type: %s" % msg_type)
                if msg_type == 0x0400:
                    # 心跳包
                    logger.debug("Received heartbeat")
                    self.last_heartbeat = time.time()
                    if writable:
                        sock.send(struct.pack("!H", 0x0400))  # type: ignore
                        logger.debug("Sent heartbeat")
            else:
                current_time = time.time()
                if current_time - self.last_heartbeat > HEARTBEAT_TIMEOUT:
                    logger.debug("heartbeat timeout")
                    break
            time.sleep(0.03)
        # 关闭连接
        sock.close()

    def run(self):
        logger.output.write("\n")
        logger.debug("Client thread started")
        self.handle_message()
        self.on_exit()

    def on_exit(self):
        global client_thread
        # self.log_file.close()
        client_thread = None
        Bladex.DeleteStringValue(KEY)
        if self.callback:
            apply(self.callback, self.callback_args)
        logger.debug("Client thread exited")


# 连接到服务器
def connect_server():
    global client_thread
    if client_thread is None:
        client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        client_socket.setblocking(0)  # 非阻塞模式 # type: ignore
        try:
            client_socket.connect((SERVER_HOST, SERVER_PORT))
        except:
            pass  # 非阻塞模式下 connect 会立即返回
        # 用 select 检测是否可写（连接成功）
        readable, writable, exceptional = select.select(
            [client_socket], [client_socket], [client_socket], 2.0
        )
        if writable:
            client_thread = ClientThread()
            client_thread.sock = client_socket
            client_thread.setDaemon(true)
            client_thread.start()
            Bladex.SetStringValue(KEY, "1")
            printx("success")
            return 1
        else:
            client_socket.close()
            printx("fail")
    return 0


# 自动连接
def auto_connect():
    if Bladex.GetStringValue(KEY):
        logger.debug("reconnecting...")
        result = connect_server()
        if result == 0:
            Bladex.DeleteStringValue(KEY)
            printx("Failed to connect to server")


# 断开服务器连接
def disconnect_server(callback=None, callback_args=()):
    global client_thread
    if client_thread is not None:
        # client_thread.sock.close()
        # client_thread.join()
        # client_thread = None
        logger.debug("Disconnecting...")
        client_thread.callback = callback
        client_thread.callback_args = callback_args

        client_thread.sock_lock.release()


############################
auto_connect()
