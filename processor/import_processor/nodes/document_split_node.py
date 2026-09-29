import json
import re
from multiprocessing.process import parent_process
from pathlib import Path
from typing import Tuple, List, Dict, Any

from langchain_text_splitters import RecursiveCharacterTextSplitter

from processor.import_processor.base import BaseNode, T
from processor.import_processor.exceptions import StateFieldError
from processor.import_processor.state import ImportGraphState
from utils.markdown_util import MarkdownTableLinearizer


class DocumentSplitNode(BaseNode):
    name = "document_split_node"
    def process(self, state: ImportGraphState) -> ImportGraphState:
        #1. 参数校验
        new_md_content,file_title,max_content_length,min_content_length = self._validate_state(state)
        #2. 按标题切分
        sections_by_head = self._split_by_head(new_md_content,file_title)
        #3. 二次切分或者合并
        final_sections = self._split_and_merge(sections_by_head,max_content_length,min_content_length)
        #4. 将切分完的内容，组装成后续节点可直接使用的chunks
        chunks = self._assemble_chunks(final_sections)
        #5. 将chunks备份成json文件，便于后续测试
        self._backup_chunks(chunks,state)

        #6. 将切分后的内容存到state中
        state["chunks"] = chunks
        return state

    def _validate_state(self, state:ImportGraphState) -> Tuple[str, str,int,int]:
        #1. 统一换行符: 将md_content中的"\r"替换成"\n"、"\r\n"替换成"\n\n"
        #1.1 从state中获取md_content
        md_content = state.get("md_content","")
        new_md_content = md_content.replace("\r","\n").replace("\r\n","\n\n")
        #2. 校验配置信息: 一个切片的最大长度、一个切片的最小长度
        max_content_length = self.config.max_content_length
        min_content_length = self.config.min_content_length
        if not max_content_length or max_content_length <= 0 or not min_content_length or min_content_length <= 0 or max_content_length < min_content_length :
            self.logger.error(f"max_content_length={max_content_length} 或者 min_content_length={min_content_length}配置错误,请检查")
            raise StateFieldError(node_name=self.name,field_name="max_content_length or min_content_length",expected_type=int)
        #3. 获取文档标题(给后续步骤作为兜底使用)
        file_title = state.get("file_title")
        #4. 将md_content, file_title, config.max_content_length, config.min_content_length给下一步使用
        return new_md_content,file_title,max_content_length,min_content_length

    def _split_by_head(self, md_content:str, file_title:str) -> List[Dict[str,Any]]:
        """
        我们最终得到的产物是切成的块列表，我们分每一块是什么结构:
        {
            "body":这块的正文内容,
            "title":这块的标题,
            "parent_title":这块的父标题,
            "file_title":这块所在的文档标题
        }
        :param new_md_content:
        :param file_title:
        :return:
        """
        #1. md_content按行切分
        md_lines = md_content.split("\n")
        #定义匹配md标题的正则heading_re = re.compile(r"^\s*(#{1,6})\s+(.+)")
        heading_re = re.compile(r"^\s*(#{1,6})\s+(.+)")
        code_fence_pattern = re.compile(r"^\s*```")
        in_code_fence = False
        #声明hierarchy列表用于存储各级标题,目的是为了识别父标题
        hierarchy = [""]*7
        #2. 遍历md_content的每一行，判断是否遇到了标题，但是注意要排除代码块的干扰
        #声明变量body，用来存储当前标题快section的内容部分
        body_lines = []
        #声明变量current_title，表示当前标题
        current_title = ""
        #声明变量current_level，表示当前标题的层级
        current_level = 0
        # 声明变量final_sections,用来存储所有的块
        final_sections = []
        # 声明一个内部方法,用来将某个标题块进行收集
        def _flush():
            """
            {
                "body":这块的正文内容,
                "title":这块的标题,
                "parent_title":这块的父标题,
                "file_title":这块所在的文档标题
            }
            :return:
            """
            # 收集body的内容
            body = "\n".join(body_lines)
            # 收集title
            title = current_title

            #判断是否存在current_title、是否存在body，如果都不存在，则不收集该段内容
            if not body and not title:
                return

            # 如果title没值，就使用file_title给其进行兜底
            title = title if title else file_title


            # 收集parent_title,从当前标题往前遍历hierarchy数组
            parent_title = ""
            for i in range(current_level - 1,0,-1):
                if hierarchy[i] != "":
                    parent_title = hierarchy[i]
                    break

            section = {
                "body":body,
                "title":title,
                "parent_title":parent_title if parent_title else title,
                "file_title":file_title
            }

            #将section添加到final_sections中
            final_sections.append(section)


        for md_line in md_lines:
            #2.1 判断md_line是不是标题行，并且不在代码围栏中
            if code_fence_pattern.match(md_line):
                in_code_fence = not in_code_fence

            match = heading_re.match(md_line)
            if match and not in_code_fence:
                # 当前行是标题行，并且没有在代码块中
                # 收集上一个标题块的section
                _flush()
                # 设置当前标题的值
                current_title = md_line
                # 清空body_lines
                body_lines = []
                # 将当前标题添加到hierarchy数组中,并且要记录当前标题的层级
                # 获取当前标题的层级:就是#的个数，使用正则匹配的第一个捕获组能拿到#的个数
                current_level = len(match.group(1))
                # 将当前标题存储到hierarchy数组中的current_level
                hierarchy[current_level] = current_title
                # 清空hierarchy中current_level下表后的所有元素
                for i in range(current_level+1,7):
                    hierarchy[i] = ""
            else:
                # 当前行不是标题行，或者当前行在代码块中，将当前行的内容添加到当前section的body中
                body_lines.append(md_line)

        # 遍历到最后，遇不到title了，要将前一个title的所有内容收集起来
        _flush()

        return final_sections

    #二次切分与合并
    def _split_and_merge(self, sections:List[Dict[str,Any]], max_content_length:int, min_content_length:int) -> List[Dict[str,Any]]:
        #1. 声明current_sections用于收集二次切分后的section
        current_sections = []
        #2. 遍历每一个section,对每一个section进行二次切分
        for section in sections:
            split_sections = self._split_long_section(section,max_content_length)
            current_sections.extend(split_sections)

        #3. 针对小的section进行合并
        final_sections = self._merge_short_section(current_sections,min_content_length)
        #4. 返回二次切分和合并后的section
        return final_sections

    def _split_long_section(self, section:Dict[str,Any], max_content_length:int) -> List[Dict[str,Any]]:
        """
        {
            "body":这块的正文内容,
            "title":这块的标题,
            "parent_title":这块的父标题,
            "file_title":这块所在的文档标题
        }
        :param section:
        :param max_content_length:
        :return:
        """
        #1. 判断section的大小是否超过了max_content_length
        #1.1. 计算section的长度
        #1.1.1 获取section的title
        title = section.get("title")
        # 防御性编程:如果title太长了，我们只取title的前80个字符
        if len(title) > 80:
            title = title[:80]

        title_prefix = title + "\n\n"
        #1.1.2 获取body
        body = section.get("body")

        # 对body中的表格进行处理
        if "<table>" in body:
            body = MarkdownTableLinearizer.process(body)
            section["body"] = body

        #1.1.3 计算长度
        total_length = len(body) + len(title_prefix)

        #1.2 判断total_length是否大于max_content_length
        if total_length <= max_content_length:
            # 说明当前section的长度没有超过最大长度，不需要切分

            return [section]

        # 计算可切分的长度=最大长度-title_prefix的长度
        split_content_length = max_content_length - len(title_prefix)

        # 当前section的长度超过了最大长度,需要切分,使用RecursiveCharacterTextSplitter文本切分器进行切分
        text_splitter = RecursiveCharacterTextSplitter(
            separators=["\n\n", "\n", "。", "？", "！", "；", ".", "?", "!", ';', " ", ""],
            chunk_size=split_content_length,
            keep_separator=True,
            chunk_overlap=0
        )

        # 使用text_splitter对body进行切分
        split_body_list = text_splitter.split_text(body)
        # 判断切分后的内容是否有多个字符串
        if len(split_body_list) == 1:
            # 说明其实没有对这个section进行切分
            return [section]
        # 如果切分成了多个字符串,那么我们需要遍历切分后的字符串列表，将每一个字符串组装成一个section
        result_sections = []
        for index,split_body in enumerate(split_body_list):
            split_section = {
                "body":split_body,
                "title":f"{title}_{index + 1}",
                "parent_title": section.get("parent_title"),
                "file_title": section.get("file_title")
            }

            result_sections.append(split_section)

        return result_sections

    #合并短section
    def _merge_short_section(self, current_sections:List[Dict[str,Any]], min_content_length:int) -> List[Dict[str,Any]]:
        """
        合并短的section
        :param current_sections:
        :param min_content_length:
        :return:
        """
        #1. 获取下标为0的section，记录为current_section
        current_section = current_sections[0]
        #2. 定义final_sections用于收集合并后的section列表
        final_sections = []
        #3. 从下标为1的section遍历到最后,遍历出来的section记录为next_section
        for i in range(1,len(current_sections)):
            next_section = current_sections[i]
            #3.1 判断next_section与current_section是否是同源: parent_title是否相同
            same_parent = current_section.get("parent_title") == next_section.get("parent_title")
            #3.2 判断current_section的长度是否小于min_content_length
            current_section_body = current_section.get("body")
            is_short = len(current_section_body) < min_content_length
            #3.3 如果上面两个条件都满足，则使用current_section合并next_section
            if is_short and same_parent:
                #3.3.1 使用"\n\n"拼接current_section与next_section的body
                merged_body = current_section_body + "\n\n" + next_section.get("body")
                #3.3.2 将合并后的body赋给current_section
                current_section["body"] = merged_body
                #3.3.2 将合并后的section的标题title设置成他的parent_title，因为合并后用谁的标题都不合适，改成parent_title最合适
                current_section["title"] = current_section.get("parent_title")


            else:
                #3.4 如果不满足，则表示当前section不需要合并
                #3.4.1 将current_section添加到final_sections中
                final_sections.append(current_section)
                #3.4.2 将current_section的指针指向next_section继续往下遍历
                current_section = next_section

        # 4. 遍历完之后,将最后一个current_section添加到final_sections中
        final_sections.append(current_section)
        # 5.返回final_sections
        return final_sections

    def _assemble_chunks(self, final_sections:List[Dict[str,Any]]) -> List[Dict[str,Any]]:
        """
        原本的section:
        {
            "body":这块的正文内容,
            "title":这块的标题,
            "parent_title":这块的父标题,
            "file_title":这块所在的文档标题
        }
        我们真正需要的chunk:
        {
            "content":这块是title拼接body的内容,
            "title":这块的标题,
            "parent_title":这块的父标题,
            "file_title":这块所在的文档标题
        }
        :param final_sections:
        :return:
        """
        #1. 声明一个chunks列表，用来存储封装后的chunk
        chunks = []
        #2. 遍历sections，每一个section对应一个chunk
        for section in final_sections:
            title = section.get("title")
            body = section.get("body")
            chunk = {
                "content": f"{title}\n\n{body}",
                "title": title,
                "parent_title": section.get("parent_title"),
                "file_title": section.get("file_title")
            }
            chunks.append(chunk)
        return chunks

    #备份chunks
    def _backup_chunks(self, chunks:List[Dict[str,Any]],state:ImportGraphState):
        #1. 指定备份文件的路径
        #1.1 获取文件输出的目录
        md_path = state.get("md_path")
        md_path_obj = Path(md_path)
        file_dir = state.get("file_dir")
        file_dir_obj = Path(file_dir)
        backup_dir = file_dir_obj / md_path_obj.stem
        #1.2 判断该目录是否真实存在，如果不存在则创建目录
        backup_dir.mkdir(parents=True,exist_ok=True)
        #1.3 指定备份文件的路径
        backup_file_path = backup_dir / "chunks.json"

        #2. 将chunks写入到备份文件中
        try:
            with open(backup_file_path, "w", encoding="utf-8") as f:
                json.dump(chunks, f, ensure_ascii=False, indent=4)
        except Exception as e:
            self.logger.warning(f"{md_path_obj.stem}文件备份成chunks.json失败,但是不影响主流程")


if __name__ == '__main__':
    #1. 将new.md的内容读取出来
    document_split_node = DocumentSplitNode()

    md_path = r"D:\workspace\pycharm\shopkeeper-brain-BJ0108\knowledge\processor\import_processor\output_dir\万用表RS-12的使用\万用表RS-12的使用_new.md"

    with open(md_path, "r", encoding="utf-8") as f:
        md_content = f.read()

    init_state = {
        "md_path":r"D:\workspace\pycharm\shopkeeper-brain-BJ0108\knowledge\processor\import_processor\output_dir\万用表RS-12的使用\万用表RS-12的使用.md",
        "md_content": md_content,
        "file_title": "万用表RS-12的使用_new.md",
        "file_dir": r"D:\workspace\pycharm\shopkeeper-brain-BJ0108\knowledge\processor\import_processor\output_dir"
    }

    document_split_node(state=init_state)