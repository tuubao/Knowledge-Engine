import base64
import re
from logging import Logger
from pathlib import Path
from typing import Tuple, List, Dict

from openai import OpenAI

from processor.import_processor.base import BaseNode, T
from processor.import_processor.config import ImportConfig
from processor.import_processor.exceptions import StateFieldError, FileProcessingError
from processor.import_processor.state import ImportGraphState
from utils.clients.ai_clients import AIClients
from utils.clients.storage_clients import StorageClients


class ImageContext:
    head_title:str
    pre_context:str
    post_context:str
    def __init__(self,head_title:str,pre_context:str,post_context:str):
        self.head_title = head_title
        self.pre_context = pre_context
        self.post_context = post_context

class ImageInfo:
    image_name:str
    image_path:str
    image_context:ImageContext
    def __init__(self,image_name:str,image_path:str,image_context:ImageContext):
        self.image_name = image_name
        self.image_path = image_path
        self.image_context = image_context

class _MdFileHandler:
    def __init__(self,logger:Logger,node_name:str):
        self.logger = logger
        self.node_name = node_name

    def read_md(self,md_path:str) -> Tuple[str,Path,Path]:
        #1. 校验md_path是否为空
        if not md_path:
            self.logger.error("md_path 不能为空")
            raise StateFieldError(node_name=self.node_name,field_name="md_path",expected_type=str)
        #2. 校验md_path是否存在
        md_path_obj = Path(md_path)
        if not md_path_obj.exists():
            self.logger.error(f"md_path '{md_path}' 不存在")
            raise FileProcessingError(node_name=self.node_name,message=f"md_path'{md_path}'不存在")
        #3. 读取md文件的内容到内存
        with open(md_path_obj, 'r', encoding='utf-8') as f:
            md_content = f.read()
        #4. 获取md文件的图片的目录路径
        image_dir_obj = md_path_obj.parent / "images"

        #5. 返回md_content,md_path_obj,image_dir_obj
        return md_content,md_path_obj,image_dir_obj

    def backup_md(self,md_content:str,md_path:str) -> None:
        #1. 构建备份文件的路径,在原文件路径下，但是名字叫做  原文件名_new.原文件后缀
        md_path_obj = Path(md_path)
        backup_md_path_obj = md_path_obj.parent / (md_path_obj.stem + "_new" + md_path_obj.suffix)
        #2. 将md_content写入到备份文件中
        try:
            with open(backup_md_path_obj, 'w', encoding='utf-8') as f:
                f.write(md_content)
        except Exception as e:
            self.logger.warning(f"备份md文件失败: {e},但是不影响程序的运行")
        self.logger.info(f"文件备份成功，文件路径是{str(backup_md_path_obj)}")

class _ImageScanner:
    def __init__(self,config:ImportConfig):
        self.config = config
    def scan_img_dir(self,image_dir_obj:Path,md_content:str) -> Tuple[List[ImageInfo],List[str]]:

        image_info_list = []

        for image_file in image_dir_obj.iterdir():
            # 1 过滤子目录
            if not image_file.is_file():
                continue
            # 2 过滤非图片文件
            if image_file.suffix not in self.config.image_extensions:
                continue
            # 3 在md_content中匹配到图片所在的行
            # 3.1 将md_content按行进行切分
            md_lines = md_content.split("\n")
            # 3.2 遍历出md的每一行
            # 声明匹配md中的图片的正则表达式
            pattern = re.compile(r"!\[.*?\]\(.*?" + re.escape(image_file.name) + r".*?\)")

            #默认没在代码块中
            in_code_fence = False
            #定义匹配代码块的正则表达式
            code_fence_pattern = re.compile(r"^\s*```")
            for index,md_line in enumerate(md_lines):
                # 3.3 判断其是否在代码块中
                if code_fence_pattern.match(md_line):
                    in_code_fence = not in_code_fence

                # 3.4 判断是否匹配到图片
                if in_code_fence or not pattern.match(md_line):
                    continue
                # 3.5 到这就表示确实已经匹配上这张图片了,就要开始查找这张图片的上下文
                # 3.5.1 查找图片的上文
                # 定义匹配标题的正则表达式
                heading_pattern = re.compile(r'^#{1,6}\s+(.+)$')
                head_title,head_content = self._find_heading_content(md_lines,heading_pattern,index)

                #3.5.2 查找图片的下文
                post_content = self._find_post_content(index,md_lines,heading_pattern)

                #3.6 根据配置中的最大长度，对图片的上文、下文进行截取
                img_content_length = self.config.img_content_length
                #3.6.1 截取上文内容
                pre_context = self._extract_image_context(head_content,img_content_length,"up")
                #3.6.2 截取下文内容
                post_context = self._extract_image_context(post_content,img_content_length,"down")

                #3.7 将图片的上下文封装到一个对象中
                image_context = ImageContext(head_title =head_title,pre_context=pre_context,post_context=post_context)

                #4. 组装ImageInfo对象
                image_info = ImageInfo(image_name=image_file.name,image_path=str(image_file),image_context=image_context)

                image_info_list.append(image_info)

        return image_info_list,md_lines






    #查找图片上文的方法
    def _find_heading_content(self,md_lines:List[str],heading_pattern,image_index:int) -> Tuple[str,List[str]]:
        # 定义找到的最近的标题的索引
        head_title_index = -1
        head_title = ""
        #1. 从当前图片的索引向前遍历，一直遍历到最前面，如果找到了最近的标题就停止循环，如果一直没找到才遍历到最前面

        in_code_fence = False
        code_fence_pattern = re.compile(r"^\s*```")
        for i in range(image_index - 1,-1,-1):
            # 匹配标题
            line = md_lines[i]
            # 遇到代码块的标志就反转in_code_fence
            if code_fence_pattern.match(line):
                in_code_fence = not in_code_fence

            if heading_pattern.match(line) and not in_code_fence:
                # 找到标题了
                head_title_index = i
                head_title = line
                break
        #2. 获取图片的上文
        head_content = md_lines[head_title_index + 1:image_index]

        return head_title,head_content

    # 查找图片下文的方法
    def _find_post_content(self,image_index:int,md_lines:List[str],heading_pattern:re.Pattern) -> List[str]:
        # 1. 从图片索引向下遍历，直到找到跟他最近的那个标题为止，如果没找到就一直向下找到最后一行
        in_code_fence = False
        code_fence_pattern = re.compile(r"^\s*```")

        post_title_index = len(md_lines)
        for i in range(image_index + 1,len(md_lines)):
            # 匹配标题
            line = md_lines[i]
            # 遇到代码块的标志就反转in_code_fence
            if code_fence_pattern.match(line):
                in_code_fence = not in_code_fence
            if not in_code_fence and heading_pattern.match(line):
                # 找到了下标题
                post_title_index = i
                break

        post_content = md_lines[image_index + 1: post_title_index]
        return post_content

    # 截取上下文内容
    def _extract_image_context(self, content:List[str], img_content_length:int,direction:str) -> str:
        image_pattern = re.compile(r'!\[.*?\]\(.*?\)')
        # 定义存放当前段落内容的容器
        current_graph = []
        # 定义存放最终的上下文所有段落的容器
        final_graphs = []

        #1. 遍历content
        for line in content:

            # 2. 判断如果line是空行，或者是其它图片，则表示一段应该结束了，要开启新的段落了
            if not line.strip() or image_pattern.match(line):
                #2.1 将当前行的内容，添加到final_graphs,并且要清空current_graph
                if current_graph:
                    final_graphs.append("\n".join(current_graph))
                    current_graph = []
            else:
                # 不需要开启新的段落，就将当前行的内容添加到current_graph
                current_graph.append(line)

        # 遍历完成之后,如果current_graph还有内容,也要添加到final_graphs中
        if current_graph:
            final_graphs.append("\n".join(current_graph))
            current_graph = []

        # 遍历final_graphs，对长度进行判断，如果超过了最大长度，就进行截取
        extract_graphs = []

        total_length = 0

        # 如果是截取上文，那么应该先将final_graphs进行反转
        if direction == "up":
            final_graphs.reverse()

        for graph in final_graphs:
            if total_length > img_content_length:
                break
            extract_graphs.append(graph)
            total_length += len(graph) + len("\n\n")

        # 在截取完之后，拼接字符串之前，判断如果是截取上文，那么需要将extract_graphs再次反转过来
        if direction == "up":
            extract_graphs.reverse()

        # 最终返回收集到的段落
        return "\n\n".join(extract_graphs)

class _VLMSummarizer:
    def __init__(self,logger:Logger,config:ImportConfig):
        self.logger = logger
        self.config = config

    def summarize_all(self,document_name,image_info_list:List[ImageInfo]):
        # 存储每张图片的摘要信息，key:图片名字，value:图片摘要信息
        image_summaries = {}
        #1. 创建VLM模型对象
        try:
            vlm_client = AIClients.get_vlm_client()
        except ConnectionError as e:
            self.logger.warning(f"无法连接到VLM模型，图片描述信息将无法生成: {e}")
            # 兜底: 需要给每张图片设置描述信息为 "暂无摘要信息"
            for image_info in image_info_list:
                image_summaries[image_info.image_name] = "暂无摘要信息"
            return image_summaries

        #2.遍历每一张图片，给每一张图片生成摘要信息
        for image_info in image_info_list:
            # 调用vlm模型获取图片的摘要信息
            image_summarize = self._summarize_single(document_name,image_info,vlm_client)

            image_summaries[image_info.image_name] = image_summarize

        return image_summaries

    def _summarize_single(self,document_name:str, image_info:ImageInfo, vlm_client:OpenAI):
        #1. 获取图片上下文信息
        image_context = image_info.image_context
        #2. 将图片的上下文信息组装成字符串
        final_context = f"{image_context.head_title} \n {image_context.pre_context} \n {image_context.post_context}"

        #3. 读取图片
        image_path = image_info.image_path
        with open(image_path,"rb") as f:
            image_data = base64.b64encode(f.read()).decode("utf-8")

        # 1. 组装给大模型的输入信息
        messages = [
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": (
                            f"任务：为Markdown文档中的图片生成一个简短的中文标题。\n"
                            f"背景信息：\n"
                            f"  1. 所属文档标题：\"{document_name}\"\n"
                            f"  2. 图片上下文：{final_context}\n"
                            f"请结合图片内容和上述上下文信息，"
                            f"用中文简要总结这张图片的内容，"
                            f"生成一个精准的中文标题摘要（不要包含图片二字）。"
                        ),
                    },
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/jpeg;base64,{image_data}"
                        },
                    },
                ]
            }
        ]
        # 2. 调用大模型，获取大模型的输出
        try:
            vlm_result = vlm_client.chat.completions.create(
                model=self.config.vl_model,
                messages=messages
            )
        except Exception as e:
            self.logger.warning(f"调用VLM模型失败，图片'{image_info.image_name}'的描述信息将无法生成: {e}")
            return "暂无摘要信息"

        # 3. 解析大模型的输出，拿到每张图片的描述信息
        return vlm_result.choices[0].message.content

class _ImageUploader:
    def __init__(self,logger:Logger,config:ImportConfig):
        self.logger = logger
        self.config = config
    def upload_and_replace(self,md_lines,document_name:str,image_info_list:List[ImageInfo],image_summarizes:Dict[str,str]) -> str:
        #1. 上传图片
        remote_urls = self._upload_all(document_name,image_info_list)
        print(remote_urls)
        #2. 替换md中的内容,返回替换之后的md的内容
        new_md_content = self._replace_md_content(md_lines,image_summarizes,remote_urls)

        return new_md_content

    def _upload_all(self,document_name:str,image_info_list:List[ImageInfo]) -> Dict[str, str]:
        # 存放每张图片在MinIO服务器上的访问路径
        remote_urls = {}
        # 1. 创建MinIO客户端对象
        try:
            minio_client = StorageClients.get_minio_client()
        except ConnectionError as e:
            self.logger.warning(f"无法连接到MinIO服务器，图片将无法上传: {e}")
            # 兜底: 所有图片使用原路径
            for image_info in image_info_list:
                remote_urls[image_info.image_name] = image_info.image_path
            return remote_urls

        #2. 调用minio_client的方法进行文件上传
        for image_info in image_info_list:
            # 构建object_name: 其实就是文件存储在MinIO上的路径。文档名/图片名    万用表RS-12的使用/1.jpg
            object_name = document_name + "/" + image_info.image_name
            buket_name = self.config.minio_bucket
            try:
                minio_client.fput_object(
                    bucket_name=buket_name,
                    object_name=object_name,
                    file_path=image_info.image_path
                )
            except Exception as e:
                # 兜底使用图片的原路径
                remote_urls[image_info.image_name] = image_info.image_path
                continue

            # 组装文件在MinIO上的访问的url
            remote_url = self.config.get_minio_base_url() + "/" + buket_name + "/" + object_name

            remote_urls[image_info.image_name] = remote_url
        return remote_urls

    def _replace_md_content(self, md_lines:List[str], image_summarizes:Dict[str,str], remote_urls:Dict[str,str]) -> str:
        # 遍历md_lines
        # 定义正则表达式匹配md中的图片，定义两个匹配组出来，第一个匹配组用于匹配摘要，第二个匹配组用于匹配路径
        pattern = re.compile(r"!\[(.*?)\]\((.*?)\)")
        in_code_fence = False
        code_fence_pattern = re.compile(r"^\s*```")

        # 声明一个容器存储替换后的md_lines
        new_md_lines = []
        for line in md_lines:
            if code_fence_pattern.match(line):
                in_code_fence = not in_code_fence
            #1. 如果该行是图片，并且不在代码块里面，就替换
            match = pattern.match(line)
            if not in_code_fence and match:
                # 需要替换
                # 获取图片名
                image_name = Path(match[2]).name
                new_md_lines.append(f"![{image_summarizes[image_name]}]({remote_urls[image_name]})")
            else:
                # 不需要替换
                new_md_lines.append(line)

        return "\n".join(new_md_lines)


class MdImageNode(BaseNode):
    name = "md_image_node"

    def __init__(self):
        super().__init__()
        self.md_file_handler = _MdFileHandler(logger=self.logger, node_name=self.name)
        self.image_scanner = _ImageScanner(self.config)
        self.vlm_summarizer = _VLMSummarizer(self.logger, self.config)
        self.image_uploader = _ImageUploader(logger=self.logger, config=self.config)

    def process(self, state: ImportGraphState) -> ImportGraphState:
        #1. 读取md文件的内容到内存
        md_path = state.get("md_path")
        md_content,md_path_obj,image_dir_obj = self.md_file_handler.read_md(md_path)

        #2. 遍历图片目录中的每一个图片文件,与上面md_lines中的进行匹配
        image_info_list,md_lines = self.image_scanner.scan_img_dir(image_dir_obj,md_content)

        #4. 根据图片的上下文,使用VLM模型 识别图片、获取图片的描述信息
        image_summarizes = self.vlm_summarizer.summarize_all(document_name=md_path_obj.stem,image_info_list=image_info_list)

        #5. 将图片上传到MinIO服务器,将图片的描述信息、MinIO中的URL等信息回填到md文档中
        new_md_content = self.image_uploader.upload_and_replace(md_lines=md_lines,document_name=md_path_obj.stem,image_info_list=image_info_list,image_summarizes=image_summarizes)


        #7. 将回填后的内容，备份成新md文件（便于测试观察）
        self.md_file_handler.backup_md(new_md_content,md_path)

        state["md_content"] = new_md_content
        return state

if __name__ == '__main__':
    state = {
        "md_path":r"D:\workspace\pycharm\shopkeeper-brain-BJ0108\knowledge\processor\import_processor\output_dir\万用表RS-12的使用\万用表RS-12的使用.md"
    }

    node = MdImageNode()
    node(state)