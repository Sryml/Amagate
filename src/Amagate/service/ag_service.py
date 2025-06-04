# Author: Sryml
# Email: sryml@hotmail.com
# Python Version: 3.11
# License: GPL-3.0

from __future__ import annotations

import asyncio
import threading
import queue

#
from typing import Any, TYPE_CHECKING

#
from bpy.app.translations import pgettext

#
from ..scripts import data

############################
logger = data.logger


############################ Global variables
# 全局消息队列
message_queue = queue.Queue()
server_thread = None  # type: AsyncServerThread | None
is_connected = False

SERVER_HOST = "127.0.0.1"
SERVER_PORT = 1673

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


def get_status():
    return pgettext("Closed") if server_thread is None else f'{pgettext("Running")}...'


def get_client_status():
    return (
        pgettext("Connected", "Server") if is_connected else pgettext("Not connected")
    )


async def handle_client(reader, writer):
    # type: (asyncio.StreamReader, asyncio.StreamWriter) -> None
    global is_connected
    is_connected = True

    addr = writer.get_extra_info("peername")
    logger.info(f"Connected to {addr}")

    while True:
        try:
            # 从队列获取消息
            message = message_queue.get()
            # writer.write(message.encode())
            # await writer.drain()
        # except queue.Empty:
        #     await asyncio.sleep(0.1)
        except asyncio.IncompleteReadError:
            # 处理客户端非正常中断的情况（比如连接被重置）
            logger.debug(f"{addr} - Connection closed unexpectedly.")
            break
        except ConnectionResetError:
            # 处理连接重置的情况（通常是客户端强行关闭连接）
            logger.debug(f"{addr} - Connection reset by peer.")
            break
        except Exception as e:
            # 捕获其他未预料到的异常
            logger.debug(f"{addr} - Unexpected error: {e}")
            break

    writer.close()
    await writer.wait_closed()
    logger.info(f"Connection with {addr} closed")
    is_connected = False


# 创建服务器
async def create_server(this):
    global SERVER_PORT, server_thread

    while True:
        try:
            server = await asyncio.start_server(handle_client, SERVER_HOST, SERVER_PORT)
            logger.info(f"Server is listening on {SERVER_HOST}:{SERVER_PORT}")
            break
        except OSError:
            logger.warning(f"Port {SERVER_PORT} is not available")
            server_thread = None
            return
            # logger.warning(f"Port {SERVER_PORT} is not available, trying next port...")
            # SERVER_PORT += 1
    #
    this.server = server
    async with server:
        # 服务器永久运行
        try:
            await server.serve_forever()
        except asyncio.CancelledError:
            server_thread = None
            logger.debug("Server stopped")


class AsyncServerThread(threading.Thread):
    def __init__(self):
        super().__init__(daemon=True)
        self.loop = asyncio.new_event_loop()
        self.server = None  # type: asyncio.AbstractServer | None

    # async def handle_client(self, reader, writer):
    #     while True:
    #         try:
    #             # 从队列获取消息
    #             message = message_queue.get_nowait()
    #             writer.write(message.encode())
    #             await writer.drain()
    #         except queue.Empty:
    #             await asyncio.sleep(0.1)
    #         except ConnectionError:
    #             break

    # async def start_server(self):
    #     self.server = await asyncio.start_server(
    #         handle_client, SERVER_HOST, SERVER_PORT
    #     )  # , loop=self.loop

    #     async with self.server:
    #         await self.server.serve_forever()

    def run(self):
        asyncio.set_event_loop(self.loop)
        self.loop.run_until_complete(create_server(self))
        self.loop.close()
        # logger.debug(f"Server thread stopped")


def start_server():
    global server_thread
    if server_thread is None or not server_thread.is_alive():
        server_thread = AsyncServerThread()
        server_thread.start()
        logger.debug(f"Server thread started")
    # return server_thread


def stop_server():
    global server_thread
    if server_thread and server_thread.is_alive():

        async def shutdown():
            server_thread.server.close()
            await server_thread.server.wait_closed()

        server_thread.loop.call_soon_threadsafe(lambda: asyncio.create_task(shutdown()))
        logger.debug(f"Server thread stopped")
