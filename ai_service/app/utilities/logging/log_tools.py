import tempfile


class LogTool():
    def tail(self, file, taillines=500, return_str=True, avg_line_length=None):
        """
        file: 日志的绝对路径
        taillines：返回最后的行数
        offset:每次循环相对文件末尾指针偏移数
        return_str:返回类型，默认为字符串，False为列表。
        avg_line_length:每行字符平均数,可以默认不填
        return: str
        """
        with open(file, errors='ignore', encoding="utf-8") as f:
            if not avg_line_length:
                f.seek(0, 2)
                f.seek(f.tell() - 3000)
                avg_line_length = int(3000 / len(f.readlines())) + 10
            f.seek(0, 2)
            end_pointer = f.tell()
            offset = taillines * avg_line_length
            if offset > end_pointer:
                f.seek(0, 0)
                lines = f.readlines()[-taillines:]
                return "".join(lines) if return_str else lines
            offset_init = offset
            i = 1
            while len(f.readlines()) < taillines:
                location = f.tell() - offset
                f.seek(location)
                i += 1
                offset = i * offset_init
                if f.tell() - offset < 0:
                    f.seek(0, 0)
                    break
            else:
                f.seek(end_pointer - offset)
            lines = f.readlines()
            if len(lines) >= taillines:
                lines = lines[-taillines:]

            return "".join(lines) if return_str else lines


    def string_to_file(self, string):
        """
        字符串转字节流
        return: File()
        """
        file_like_obj = tempfile.NamedTemporaryFile()
        file_like_obj.write(string.encode("utf-8"))
        # 确保string立即写入文件
        file_like_obj.flush()
        # 将文件读取指针返回到文件开头位置
        file_like_obj.seek(0)
        return file_like_obj


log_tool = LogTool()
