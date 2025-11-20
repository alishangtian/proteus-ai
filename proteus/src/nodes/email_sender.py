"""邮件发送节点(支持QQ邮箱)"""

import aiosmtplib
import os
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.header import Header
from typing import Dict, Any
from .base import BaseNode


class EmailSenderNode(BaseNode):
    """邮件发送节点(默认使用QQ邮箱SMTP服务)

    配置说明:
    1. 在环境变量中设置:
       - EMAIL_USER: QQ邮箱完整地址(如123456@qq.com)
       - EMAIL_PASSWORD: SMTP授权码(如ruicxmzfajymbfbh)
    2. 默认使用QQ邮箱SMTP服务器(smtp.qq.com)
    3. 默认使用SSL端口465
    4. 支持UTF-8编码的邮件主题和内容
    5. 可自定义发件人显示名称

    使用步骤:
    1. 设置环境变量(在终端或配置文件中):
       export EMAIL_USER="your_email@qq.com"
       export EMAIL_PASSWORD="your_smtp_auth_code"
    2. 在代码中调用节点:
       from nodes.email_sender import EmailSenderNode

       node = EmailSenderNode()
       result = await node.execute({
           "to": "recipient@example.com",
           "subject": "测试邮件",
           "content": "这是一封测试邮件",
           "is_html": False,
           "from_name": "系统通知"  # 可选
       })

    注意:
    - 授权码(如ruicxmzfajymbfbh)需要从QQ邮箱设置中获取
    - 授权码只需在环境变量中设置一次即可重复使用
    - 不要将授权码硬编码在代码中
    - 支持HTML格式邮件(is_html=True)
    """

    async def execute(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """执行邮件发送

        Args:
            params: 包含邮件发送参数的字典，必须包含:
                - to: 收件人邮箱(多个用逗号分隔)
                - subject: 邮件主题
                - content: 邮件内容
                - is_html: 是否HTML格式(默认False)
            可选参数:
                - host: SMTP服务器地址(默认smtp.qq.com)
                - port: SMTP端口(默认465)
                - from_name: 发件人显示名称(默认使用邮箱地址)

        Returns:
            包含发送结果的字典:
                - success: 是否发送成功
                - message_id: 邮件消息ID(成功时)
                - error: 错误信息(失败时)
        """
        host = str(params.get("host", "smtp.qq.com"))
        port = int(params.get("port", 587))
        user_name = os.getenv("EMAIL_USER")
        password = os.getenv("EMAIL_PASSWORD")
        to_emails = [email.strip() for email in str(params["to"]).split(",")]
        subject = str(params["subject"])
        content = str(params["content"])
        is_html = bool(params.get("is_html", False))
        from_name = str(params.get("from_name", user_name))

        if not user_name or not password:
            return {
                "success": False,
                "message_id": None,
                "error": "未配置邮箱用户名或密码(请设置EMAIL_USER和EMAIL_PASSWORD环境变量)",
            }

        try:
            # 创建邮件消息
            message = MIMEText(content, "html" if is_html else "plain", "utf-8")
            message["From"] = Header(f"{from_name} <{user_name}>", "utf-8")
            message["To"] = Header(", ".join(to_emails), "utf-8")
            message["Subject"] = Header(subject, "utf-8")

            # 异步发送邮件
            async with aiosmtplib.SMTP(
                hostname=host, port=port, use_tls=port == 465
            ) as smtp:
                if port == 587:
                    await smtp.connect()
                    await smtp.starttls()
                await smtp.login(user_name, password)
                response = await smtp.send_message(message)

                return {
                    "success": True,
                    "message_id": message["Message-ID"],
                    "error": None,
                }

        except Exception as e:
            return {"success": False, "message_id": None, "error": str(e)}

    async def agent_execute(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """执行节点并返回统一格式结果

        Args:
            params: 节点参数

        Returns:
            Dict[str, Any]: 包含'result'键的执行结果
        """
        result = await self.execute(params)
        if result["success"]:
            return {"result": f"邮件发送成功，消息ID: {result['message_id']}"}
        return {"result": f"邮件发送失败: {result['error']}"}
