import time
import sys
import string


# python3-like print function
def printx(*values, **kwargs):
    sep = kwargs.get("sep", " ")
    end = kwargs.get("end", "\n")
    file = kwargs.get("file", None)
    flush = kwargs.get("flush", 0)

    output = string.join(map(str, values), sep)  # type: ignore
    if file is None:
        file = sys.stdout
    file.write(output)
    file.write(end)


class SimpleLogger:
    levels = {
        "DEBUG": 0,
        "INFO": 1,
        "WARNING": 2,
        "ERROR": 3,
        "CRITICAL": 4,
    }

    def __init__(self, name="root", level="INFO", output=sys.stdout):
        self.name = name
        self.output = output  # 可以是文件对象或 sys.stdout/sys.stderr
        self.formatter = (
            "[%(name)s] %(asctime)s - %(levelname)s - %(message)s"  # 默认格式
        )
        self.setLevel(level)  # 使用 setLevel 初始化

    def setLevel(self, level):
        self.level = self.levels.get(level, 1)

    def setFormatter(self, fmt):
        """设置日志格式（类似 logging.Formatter）"""
        self.formatter = fmt

    def _should_log(self, level):
        """检查是否应该输出日志"""
        return self.levels.get(level, 1) >= self.level

    def _format_message(self, level, msg):
        """格式化日志消息（使用 % 格式化）"""
        log_data = {
            "asctime": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(time.time())),
            "levelname": level,
            "name": self.name,
            "message": msg,
        }
        return self.formatter % log_data + "\n"

    def log(self, level, msg):
        """核心日志方法"""
        if not self._should_log(level):
            return
        log_line = self._format_message(level, msg)
        try:
            self.output.write(log_line)
            if hasattr(self.output, "flush"):  # 确保立即写入（如文件）
                self.output.flush()
        except:
            pass
            # sys.stderr.write("!!! Failed to write log: " + log_line)

    def debug(self, msg):
        self.log("DEBUG", msg)

    def info(self, msg):
        self.log("INFO", msg)

    def warning(self, msg):
        self.log("WARNING", msg)

    def error(self, msg):
        self.log("ERROR", msg)

    def critical(self, msg):
        self.log("CRITICAL", msg)


############################
log_file = "../../bin/AmagateClient.log"

logger = SimpleLogger("Amagate", level="DEBUG", output=open(log_file, "a"))
