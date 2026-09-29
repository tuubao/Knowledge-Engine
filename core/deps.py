from functools import cache

from service.file_process_service import FileProcessService
from service.query_service import QueryService


@cache
def get_file_process_service():
    return FileProcessService()

@cache
def get_query_service():
    return QueryService()