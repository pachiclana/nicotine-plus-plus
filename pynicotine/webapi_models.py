from pydantic import BaseModel, Field
from typing import Optional
from uuid import uuid4

class WebApiSearchResult(BaseModel):

    id: str = Field(default_factory=lambda: uuid4().hex)
    user: str
    ip_address: str
    port: int
    has_free_slots: bool
    inqueue: int
    ulspeed: int
    file_name: str
    file_extension: str
    file_path: str
    file_size: int
    file_h_length: str
    bitrate: int
    search_similarity: float
    file_attributes: Optional[dict] = None

class FileDownloadedNotification(BaseModel):
    user: str
    virtual_file_path: str
    file_download_path: str

class WebApiSearchModel(BaseModel):
    search_term: str
    wait_for_seconds: int
    search_filters: Optional[dict] = None
    smart_filters: Optional[bool] = None

class FileToDownload(BaseModel):
    search_result_id: str
    # file_owner: str
    # file_virtual_path: str
    # file_size: int
    # file_attributes: Optional[dict] = None

class TransferModel(BaseModel):
    username: str
    virtual_path: str
    download_path: str
    status: str
    size: int
    current_byte_offset: Optional[int] = None
    download_percentage: Optional[str] = None
    file_attributes: Optional[dict] = None

class SearchReqResponseModel(BaseModel):
    pass

class SearchResultModel(BaseModel):
    pass