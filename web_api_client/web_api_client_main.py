    
from fastapi import FastAPI
import uvicorn
import asyncio
from pydantic import BaseModel
from typing import Optional

class WebApiSearchResult(BaseModel):
    token: int
    user: str
    ip_address: str
    port: int
    has_free_slots: bool
    inqueue: int
    ulspeed: int
    file_name: str
    file_extension: str
    file_path: str
    bitrate: int
    search_similarity: float
    file_attributes: Optional[dict] = None

class FileDownloaded(BaseModel):
    user: str
    virtual_file_path: str
    file_download_file: str

app = FastAPI()

@app.post("/response/search/global")
async def root(search_result: WebApiSearchResult):
    print(search_result.file_name)
    return search_result

@app.post("/download/notification")
async def root(download: FileDownloaded):
    print(download.file_download_file)
    return download

if __name__ == "__main__":
    asyncio.run(uvicorn.run(app, port=7771, log_level="critical"))