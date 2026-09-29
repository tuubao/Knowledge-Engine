import logging
import shutil
import time
import zipfile
from pathlib import Path
import requests
from processor.import_processor.base import BaseNode, T
from processor.import_processor.config import ImportConfig
from processor.import_processor.exceptions import ValidationError
from processor.import_processor.state import ImportGraphState


class PdfToMdNode(BaseNode):
    name = "pdf_to_md_node"
    def process(self, state: ImportGraphState) -> ImportGraphState:
        #1. 上传并轮询MinerU的解析结果
        self.log_step(step_name="Step1", message="上传PDF到MinerU并轮询解析结果")
        pdf_path = state.get("pdf_path")
        pdf_path_obj = Path(pdf_path)
        zip_url = self._upload_pdf_and_query_result(self.config,pdf_path_obj)

        #2. 下载ZIP并提取MD文件
        self.log_step(step_name="Step2", message="下载Zip并解压")
        file_dir = state.get("file_dir")
        file_dir_obj = Path(file_dir)
        md_path = self._extract_md(zip_url,file_dir_obj,pdf_path_obj)
        #3. 将md_path存入state中
        state['md_path'] = md_path
        return state

    def _upload_pdf_and_query_result(self,config:ImportConfig,pdf_path_obj:Path) -> str:
        #1. 检查MinerU的配置
        mineru_api_token = config.mineru_api_token
        mineru_base_url = config.mineru_base_url
        if not mineru_api_token or not mineru_base_url:
            self.logger.error("mineru_api_token or mineru_base_url not set")
            raise ValidationError(node_name=self.name,message="mineru_api_token or mineru_base_url not set")

        #2. 获取文件上传链接
        #2.1 构建url
        url = mineru_base_url + "/file-urls/batch"
        #2.2 构建请求头
        header = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {mineru_api_token}"
        }

        #2.3 构建请求体
        data = {
            "files": [
                {"name": f"{pdf_path_obj.name}", "data_id": "abcd"}
            ],
            "model_version": "vlm"
        }
        #2.4 发送请求，获取上传链接
        try:
            response = requests.post(url, headers=header, json=data)
        except Exception as e:
            self.logger.error(f"【获取上传链接】接口调用失败，异常信息：{str(e)}")
            raise RuntimeError(f"【获取上传链接】接口调用失败，异常信息：{str(e)}")

        #2.5 判断请求是否成功,包含:http响应状态码是否是200
        if response.status_code != 200:
            # 说明Http请求失败，整个流程终止
            self.logger.error(f"【获取上传链接】接口调用失败，状态码：{response.status_code}，响应内容：{response}")
            raise RuntimeError(f"【获取上传链接】接口调用失败，状态码：{response.status_code}，响应内容：{response}")

        #2.6 获取到响应结果
        result = response.json()
        #2.7 判断业务状态码
        if result["code"] != 0:
            # 说明获取上传链接没有成功
            self.logger.error(f"【获取上传链接】获取链接失败，业务状态码：{result["code"]}，响应内容：{result}")
            raise RuntimeError(f"【获取上传链接】获取链接失败，业务状态码：{result["code"]}，响应内容：{result}")
        #2.8 拿到上传链接和batch_id
        batch_id = result["data"]["batch_id"]
        upload_url = result["data"]["file_urls"][0]
        self.logger.info(f"【获取上传链接】成功获取到上传链接，batch_id:{batch_id}, upload_url:{upload_url}")

        #3. 上传PDF文件到MinerU
        #3.1 发送请求上传PDF
        try:
            with open(str(pdf_path_obj), "rb") as f:
                file_content = f.read()
                res_upload = requests.put(upload_url, data=file_content)
        except Exception as e:
            self.logger.error(f"【上传PDF】上传PDF失败，异常信息：{str(e)}")
            raise RuntimeError(f"【上传PDF】上传PDF失败，异常信息：{str(e)}")

        #3.2 判断状态码表示是否上传成功
        if res_upload.status_code != 200:
            self.logger.error(f"【上传PDF】上传PDF失败，状态码：{res_upload.status_code}，响应内容：{res_upload}")
            raise RuntimeError(f"【上传PDF】上传PDF失败，状态码：{res_upload.status_code}，响应内容：{res_upload}")

        self.logger.info(f"【上传PDF】成功上传PDF文件到MinerU，文件名：{pdf_path_obj.name}，batch_id:{batch_id}")

        #4. 轮询查询解析结果，直到成功、失败或超时
        #定义最大超时时间
        max_time = 30

        # 定义轮询的时间间隔
        interval_time = 3

        #定义开始时间
        start_time = time.time()
        while True:
            end_time = time.time()
            if end_time - start_time > max_time:
                # 如果耗时超过了最大超时时间，则终止轮询
                self.logger.warning(f"【轮询解析结果】轮询超时，轮询时间：{end_time - start_time:.2f}s，batch_id: {batch_id}")
                break
            pull_url = mineru_base_url + f"/extract-results/batch/{batch_id}"
            pull_res = requests.get(pull_url, headers=header)
            # 判断响应状态码,如果不是200, 则表示查询失败
            if pull_res.status_code != 200:
                self.logger.warning(f"【轮询解析结果】失败, 状态码为:{pull_res.status_code}")

                #休息三秒再轮询
                time.sleep(interval_time)
                continue
            # 判断业务响应码
            pull_result = pull_res.json()
            if pull_result['code'] != 0:
                self.logger.warning(f"【轮询解析结果】业务失败, 业务状态码为:{pull_result['code']}")

                time.sleep(interval_time)
                continue

            # 获取解析结果
            extract_result = pull_result['data']['extract_result']
            # 获取解析状态
            extract_state = extract_result[0]['state']
            if extract_state == "done":
                # 表示MinerU真正完成了Pdf转Md的任务
                full_zip_url = extract_result[0]['full_zip_url']
                self.logger.info(f"【轮询解析结果】MinerU解析成功, batch_id:{batch_id}, full_zip_url:{full_zip_url}")
                return full_zip_url
            elif extract_state == "failed":
                # 表示MinerU转换Pdf成Md失败了
                self.logger.error(f"【轮询解析结果】MinerU解析失败, batch_id:{batch_id}")
                raise RuntimeError(f"【轮询解析结果】MinerU解析失败, batch_id:{batch_id}")
            else:
                # 表示其它状态，还没转换成功，需要继续轮询
                time.sleep(interval_time)
                continue

    def _extract_md(self, zip_url:str,file_dir_obj:Path,pdf_file_obj:Path) -> str:
        #1. 发送get请求下载zip包-----> response
        try:
            res = requests.get(zip_url, timeout=20)
        except Exception as e:
            self.logger.error(f"下载zip包失败,失败信息是{str(e)}")
            raise RuntimeError(f"下载zip包失败,失败信息是{str(e)}")

        if res.status_code != 200:
            self.logger.error(f"下载zip包失败，状态码：{res.status_code}，响应内容：{res}")
            raise RuntimeError(f"下载zip包失败，状态码：{res.status_code}，响应内容：{res}")
        self.logger.info(f"成功下载zip包，zip_url:{zip_url}，文件名：{pdf_file_obj.name}")


        #2. 指定zip包的存储路径,将下载下来的zip包写到该路径下
        #2.1 构建zip包的存储路径: 就是放在file_dir/文件名_result.zip
        zip_path = file_dir_obj / f"{pdf_file_obj.stem}_result.zip"
        #2.2 将response中的内容写入到zip包存储路径下
        try:
            with open(zip_path, "wb") as f:
                f.write(res.content)
        except Exception as e:
            self.logger.error(f"保存zip包失败,失败信息是{str(e)}")
            raise RuntimeError(f"保存zip包失败,失败信息是{str(e)}")

        self.logger.info(f"成功保存zip包，zip_path:{zip_path}")

        #3. 解压zip包
        #3.1 构建zip包的解压路径: file_dir/文件名，例如: output_dir/万用表RS-12的使用/
        extract_path = file_dir_obj / f"{pdf_file_obj.stem}"
        #3.2 如果该目录下已经有内容了，要先清除该目录下的所有内容
        try:
            if extract_path.exists():
                shutil.rmtree(extract_path)
        except Exception as e:
            self.logger.warning(f"清除解压目录失败,失败信息是{str(e)}, 目录路径是{extract_path}，但不影响后续解压")
        #3.3 将zip的内容解压到解压路径下
        try:
            with zipfile.ZipFile(zip_path,"r") as zip_ref:
                zip_ref.extractall(extract_path)
        except Exception as e:
            self.logger.error(f"解压zip包失败,失败信息是{str(e)}")
            raise RuntimeError(f"解压zip包失败,失败信息是{str(e)}")

        self.logger.info(f"解压zip包成功,解压目录为{extract_path}")

        #3.4 将md文件进行重命名: pdf的文件名.md
        #3.4.1 获取要重命名的文件的路径
        md_file_path = extract_path / "full.md"
        #3.4.2 指定新文件路径: extract_path / 原文件名.md
        new_md_file_path = extract_path / f"{pdf_file_obj.stem}.md"
        #3.4.3 重命名
        md_file_path.rename(new_md_file_path)

        #4 返回md文件的路径
        return str(new_md_file_path)

if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG)
    node = PdfToMdNode()

    state = {
        "pdf_path":r"D:\workspace\pycharm\shopkeeper-brain-BJ0108\knowledge\processor\import_processor\input_dir\万用表RS-12的使用.pdf",
        "file_dir":r"D:\workspace\pycharm\shopkeeper-brain-BJ0108\knowledge\processor\import_processor\output_dir"
    }

    state_result = node(state)

    print(state_result)