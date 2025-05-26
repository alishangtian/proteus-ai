from fastapi import FastAPI, HTTPException, Header, Depends
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sandbox import execute_python_code
from dotenv import load_dotenv
import os

app = FastAPI()

# 加载环境变量
load_dotenv(".env")  # 从上级目录加载.env文件

# 获取API Key
API_KEY = os.getenv("API_KEY")
if not API_KEY:
    raise ValueError("请在.env文件中配置API_KEY")


async def verify_api_key(authorization: str = Header(...)):
    """验证Bearer Token"""
    if not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=401, detail="无效的授权格式，请使用Bearer Token"
        )
    token = authorization[7:]  # 去掉"Bearer "前缀
    if token != API_KEY:
        raise HTTPException(status_code=401, detail="无效的API Token")


# 允许跨域请求
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class CodeRequest(BaseModel):
    code: str


@app.post("/v1/sandbox/run")
async def execute_code(
    request: CodeRequest, authorization: str = Depends(verify_api_key)
):
    """
    执行Python代码并返回结果

    Args:
        request: 包含Python代码的请求体

    Returns:
        dict: 包含执行结果的响应
    """
    try:
        stdout, stderr = execute_python_code(request.code)
        return {"code": 0, "stdout": stdout, "stderr": stderr}
    except Exception as e:
        return {"code": 1, "stdout": str(e), "stderr": str(e)}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)