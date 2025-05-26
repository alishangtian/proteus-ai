# action 解析异常
class ActionBadException(Exception):
    
    def __init__(self, message: str):
        self.message = message
        super().__init__(message)
