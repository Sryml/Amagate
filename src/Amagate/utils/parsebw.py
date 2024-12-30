r"""
by Sryml
python 3.11
"""

import struct
import os
import math
from typing import Any
import traceback

epsilon = 0.00001
# 允许打印
allow_print = True


def print_(*args, **kwargs):
    sector = kwargs.get("sector", -1)
    if "sector" in kwargs:
        del kwargs["sector"]
    if allow_print or sector in []:
        print(*args, **kwargs)


def round2(x: float, n: int = 3):
    if math.isnan(x):
        return 0.0
    if x == 0 or x == 1:
        return int(x)
    if isinstance(x, int):
        return x
    if abs(x) < epsilon:
        return 0.0
    split = str(x).split("e")
    if len(split) > 1:
        return float(f"{float(split[0]):.{n}f}e{split[1]}")
    return float(f"{x:.{n}f}")


def unpack(fmat: str, f) -> Any:
    fmat_ = fmat.lower()
    if fmat_[-1] == "s":
        buffer = int(fmat_[:-1])
    else:
        buffer = (
            fmat_.count("i") * 4
            + fmat_.count("f") * 4
            + fmat_.count("d") * 8
            + fmat_.count("b")
        )

    if fmat_[-1] == "s":
        return struct.unpack(fmat, f.read(buffer))[0].decode("Latin1")
    return [round2(x) for x in struct.unpack(fmat, f.read(buffer))]


# def handler7004(f, type_):
#     pass


def handler8003(mark, f, Info, i) -> Any:
    if mark:
        mark += " "
    address = f"{f.tell():X}"
    num = unpack("i", f)[0]
    for j in range(num):
        # 扇区相对索引
        rel_sector_id = unpack("i", f)[0]
        # 顶点数量
        vertex_num = unpack("i", f)[0]
        # 顶点相对索引列表
        rel_vertices = []
        for k in range(vertex_num):
            rel_vertices.append(unpack("i", f)[0])
        msg = f"{' ':<{7+4+4}}{mark}8003 {num}, rel_sector: {rel_sector_id}, rel_vertices: {rel_vertices} - {address}"
        Info.append(msg)
        print_(msg, sector=i)
    if num == 0:
        msg = f"{' ':<{7+4+4}}{mark}8003 {num} - {address}"
        Info.append(msg)
        print_(msg, sector=i)
    # if passable:
    #     # 扇区相对索引
    #     rel_sector_id = unpack("i", f)[0]
    #     # 顶点数量
    #     vertex_num = unpack("i", f)[0]
    #     # 顶点相对索引列表
    #     rel_vertices = []
    #     for k in range(vertex_num):
    #         rel_vertices.append(unpack("i", f)[0])
    #     msg = f"{' ':<{7+4+4}}{mark}8003 {passable}, rel_sector: {rel_sector_id}, rel_vertices: {rel_vertices} - {address}"
    #     Info.append(msg)
    #     print_(msg, sector=i)
    # else:
    #     msg = f"{' ':<{7+4+4}}{mark}8003 {passable} - {address}"
    #     Info.append(msg)
    #     print_(msg, sector=i)


def parse(file):
    with open(file, "rb") as f:
        # 打印文件名
        print(f"=================== {os.path.basename(file)} ===================")

        data = unpack("i", f)[0]
        # 大气
        print(f"## Atmospheres: {data}")
        Atmos = ([], [])
        for i in range(data):
            name_len = unpack("i", f)[0]
            name = unpack(f"{name_len}s", f)
            rgb = unpack("BBB", f)
            opacity = unpack("f", f)[0]
            Atmos[0].append(name_len)
            Atmos[1].append(name)
            # 打印大气信息
            print(f"{name}, RGB: {rgb}, Opacity: {opacity}")
        print("")

        # 顶点
        data = unpack("i", f)[0]
        print(f"## Vertices: {data}")
        for i in range(data):
            address = f"{f.tell():X}"
            x = unpack("d", f)[0]
            y = unpack("d", f)[0]
            z = unpack("d", f)[0]
            # 打印顶点信息
            print_(f"{address} - {i}: ({x}, {y}, {z})")
        print("")

        # 扇区
        sector_num = unpack("i", f)[0]
        print(f"## Sectors: {sector_num}")
        # 是否需要中断
        is_break = False
        for i in range(sector_num):
            if is_break:
                break
            name_len = unpack("i", f)[0]
            atmo_name = unpack(f"{name_len}s", f)
            # 环境光
            ambient_rgb = unpack("BBB", f)
            factor = unpack("f", f)[0]
            unknown1 = unpack("f", f)[0]
            Unknown2 = unpack("ddd", f)
            print_(f"{i} - {atmo_name}:", sector=i)
            print_(
                f"{' ':<7}Ambient RGB: {ambient_rgb}, Factor: {factor}, Unknown1: {unknown1}, Unknown2: {Unknown2}",
                sector=i,
            )
            # 跳过12个字节
            f.seek(12, 1)
            # 内部光
            internal_rgb = unpack("BBB", f)
            factor = unpack("f", f)[0]
            unknown1 = unpack("f", f)[0]
            Unknown2 = unpack("ddd", f)
            # 跳过12个字节
            f.seek(12, 1)
            pos = unpack("ddd", f)
            print_(
                f"{' ':<7}Internal RGB: {internal_rgb}, Factor: {factor}, Unknown1: {unknown1}, Unknown2: {Unknown2}, Position: {pos}",
                sector=i,
            )

            # 面数
            face_num = unpack("i", f)[0]
            print_(f"{' ':<7}Faces: {face_num}", sector=i)
            for j in range(face_num):
                if is_break:
                    break
                address = f"{f.tell():X}"
                # 标识符,默认7001
                id1 = unpack("i", f)[0]
                if id1 not in (7001, 7002, 7003, 7004, 7005):
                    print(f"unknown face id: {id1}, Sector: {i}, Face: {j} - {address}")
                    return
                # 法向
                normal = unpack("ddd", f)
                # 距离
                distance = unpack("d", f)[0]

                if id1 == 7002:
                    # 顶点数量
                    vertex_num = unpack("i", f)[0]
                    # 顶点索引列表
                    share_vertices = []
                    for k in range(vertex_num):
                        share_vertices.append(unpack("i", f)[0])
                    # 连接的扇区
                    sector_id = unpack("i", f)[0]

                if id1 == 7005:
                    # 顶点数量
                    vertex_num = unpack("i", f)[0]
                    # 顶点索引列表
                    share_vertices = []
                    for k in range(vertex_num):
                        share_vertices.append(unpack("i", f)[0])
                    print_(
                        f"{' ':<{7+4}}{j}: {id1} passable, Normal: {normal}, {distance}, share vertices: {share_vertices} - {address}",
                        sector=i,
                    )
                    continue

                id2 = unpack("i", f)[0]  # 3
                if id1 != 7004 and id2 != 3:
                    # 打印文件位置
                    print(f"id2 == {id2}, not 3, Sector: {i}, Face: {j} - {address}")
                    is_break = True
                    break
                id3 = unpack("i", f)[0]  # 0

                name_len = unpack("i", f)[0]
                # 纹理名称
                texture_name = unpack(f"{name_len}s", f)
                v1 = unpack("ddd", f)
                v2 = unpack("ddd", f)
                x = unpack("f", f)[0]
                y = unpack("f", f)[0]
                f.seek(8, 1)  # 0

                if id1 == 7002:
                    print_(
                        f"{' ':<{7+4}}{j}: {id1} passable, Normal: {normal}, {distance}, {texture_name}, v1: {v1}, v2: {v2}, pos: ({x}, {y}), share vertices: {share_vertices}, Sector: {sector_id} - {address}",
                        sector=i,
                    )
                    continue

                # 包含顶点数量
                vertex_num = unpack("i", f)[0]
                # 顶点索引列表
                vertex_list = []
                for k in range(vertex_num):
                    vertex_list.append(unpack("i", f)[0])

                print_(
                    f"{' ':<{7+4}}{j}: {id1}, Normal: {normal}, {distance}, {texture_name}, v1: {v1}, v2: {v2}, pos: ({x}, {y}), Vertexs: {vertex_list} - {address}",
                    sector=i,
                )

                if id1 == 7004:
                    passable_sectors = unpack("i", f)[0]
                    print_(
                        f"{' ':<{7+4+4}}passable sectors: {passable_sectors}\n",
                        sector=i,
                    )
                    for k in range(passable_sectors):
                        # 顶点数量
                        vertex_num = unpack("i", f)[0]
                        # 顶点索引列表
                        share_vertices = []
                        for _ in range(vertex_num):
                            share_vertices.append(unpack("i", f)[0])
                        # 连接的扇区
                        sector_id = unpack("i", f)[0]
                        # 面数
                        face_num = unpack("i", f)[0]
                        print_(
                            f"{' ':<{7+4+4}}{k}: partially passable, Share vertices: {share_vertices}, Sector: {sector_id}, Faces: {face_num}",
                            sector=i,
                        )
                        for k in range(face_num):
                            normal = unpack("ddd", f)
                            address = f"{f.tell():X}"
                            distance = unpack("d", f)[0]
                            print_(
                                f"{' ':<{7+4+4+4}}{k}: Normal: {normal}, {distance} - {address}",
                                sector=i,
                            )

                    address1 = f"{f.tell():X}"
                    Info = []
                    try:
                        print_(f"sub {f.tell():X}", sector=i)
                        marks = []
                        while True:
                            address = f"{f.tell():X}"
                            mark1 = unpack("i", f)[0]
                            if mark1 in (8001, 8002):
                                marks.append(str(mark1))
                            elif mark1 == 8003:
                                vertex_num = handler8003("".join(marks), f, Info, i)
                                marks = []
                            elif mark1 in (7001, 7002, 7003, 7004, 7005):
                                f.seek(-4, 1)  # back 4
                                break
                            else:
                                mark2 = unpack("i", f)[0]
                                f.seek(-4, 1)
                                if mark2 in (15001, 15002):
                                    f.seek(-4, 1)  # back 8
                                    break
                                if mark1 in Atmos[0]:
                                    name = unpack(f"{mark1}s", f)
                                    f.seek(-mark1, 1)
                                    if name in Atmos[1]:
                                        f.seek(-4, 1)
                                        break

                                f.seek(-4, 1)
                                # 向量
                                vector = unpack("ddd", f)
                                # 距离
                                distance = unpack("d", f)[0]
                                mark2 = unpack("ii", f)
                                if mark2 == [3, 0]:
                                    name_len = unpack("i", f)[0]
                                    # 纹理名称
                                    texture_name = unpack(f"{name_len}s", f)
                                    v1 = unpack("ddd", f)
                                    v2 = unpack("ddd", f)
                                    x = unpack("f", f)[0]
                                    y = unpack("f", f)[0]

                                    f.seek(8, 1)  # 0
                                    msg = f"{' ':<{7+4+4}}Texture: Vector: {vector}, {distance}, {texture_name}, pos: ({x}, {y}) - {address}"
                                    Info.append(msg)
                                    print_(msg, sector=i)
                                else:
                                    msg = f"{' ':<{7+4+4}}Vector: {vector}, {distance} - {address}"
                                    Info.append(msg)
                                    print_(msg, sector=i)
                                    f.seek(-8, 1)  # back
                    except:
                        print(
                            f"Warning: 解析7004失败, Sector: {i}, Face: {j} - {address1}"
                        )
                        for info in Info:
                            print(info)
                        print(traceback.format_exc())
                        return

                elif id1 == 7003:
                    # 顶点数量
                    vertex_num = unpack("i", f)[0]
                    # 顶点索引列表
                    share_vertices = []
                    for _ in range(vertex_num):
                        share_vertices.append(unpack("i", f)[0])
                    # 连接的扇区
                    sector_id = unpack("i", f)[0]
                    print_(
                        f"{' ':<{7+4+4}}partially passable, Share vertices: {share_vertices}, Sector: {sector_id}",
                        sector=i,
                    )
                    # 面数
                    face_num = unpack("i", f)[0]
                    for k in range(face_num):
                        normal = unpack("ddd", f)
                        print_(f"distance {f.tell():X}", sector=i)
                        distance = unpack("d", f)[0]
                        print_(
                            f"{' ':<{7+4+4+4}}{k}: Normal: {normal}, {distance}",
                            sector=i,
                        )

            print_("")

        if is_break:
            print("Warning: 解析中断")
            return
        print("扇区解析结束")

        # 外部光数量
        light_num = unpack("i", f)[0]
        print(f"## External Lights: {light_num}")
        for i in range(light_num):
            address = f"{f.tell():X}"
            id1 = unpack("i", f)[0]
            rgb = unpack("BBB", f)
            # 强度
            strength = unpack("f", f)[0]
            # 精度
            precision = unpack("f", f)[0]
            pos = unpack("ddd", f)
            if id1 == 15002:
                # 跳过12个字节
                f.seek(12, 1)
                v = unpack("ddd", f)
                # 扇区列表
                sector_list = []
                # 分配数量
                num = unpack("i", f)[0]
                for j in range(num):
                    sector_list.append(unpack("i", f)[0])
                print_(
                    f"{i}: External, RGB: {rgb}, Strength: {strength}, Precision: {precision}, Vector: {v}, Sectors: {sector_list} - {address}"
                )
            elif id1 == 15001:
                sector = unpack("i", f)[0]
                print_(
                    f"{i}: Bulb, RGB: {rgb}, Strength: {strength}, Precision: {precision}, Position: {pos}, Sector: {sector} - {address}"
                )
            else:
                print(f"未知的外部光类型: {id1} - {address}")
                return

        # address = f"{f.tell():X}"
        v1 = unpack("ddd", f)
        v2 = unpack("ddd", f)
        print(f"## Unknown: {v1}, {v2}")

        print("")
        f.seek(4 * sector_num, 1)
        # for i in range(sector_num):
        #     group = unpack("i", f)[0]
        sector_num = unpack("i", f)[0]
        for i in range(sector_num):
            name_len = unpack("i", f)[0]
            if i + 1 == sector_num:
                name = unpack(f"{name_len}s", f)
                print(name)
            else:
                f.seek(name_len, 1)
            # name = unpack(f"{name_len}s", f)

        print("解析成功！")
        return True
