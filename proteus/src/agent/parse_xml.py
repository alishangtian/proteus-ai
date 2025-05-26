from lxml import etree
import logging

logger = logging.getLogger(__name__)


class ParseXml:
    def parse_nested_params(self, node):
        """递归解析嵌套参数"""
        params = {}
        for child in node.iterchildren():
            if len(child):  # 如果有子节点
                params[child.tag] = self.parse_nested_params(child)
            else:
                params[child.tag] = child.text
        return params

    def find_action_node(self, root):
        """查找action标签"""
        # 遍历所有节点查找action标签
        for node in root.iter():
            if node.tag == "action":
                return node
        return None

    def parse_xml_to_dict(self, xml_content, query: str = None):
        """
        解析特定格式的XML内容并返回结构化字典
        支持格式:
        <?xml version="1.0" encoding="UTF-8"?>
        <action>
            <thinking>思考内容</thinking>
            <tool_name>
                <param1>value1</param1>
                <param2>value2</param2>
            </tool_name>
        </action>
        或直接以<thinking>或<tool_name>开头的XML内容(会自动添加XML声明和<action>标签)
        也支持Markdown代码块格式的XML内容，如:
        ```xml
        <thinking>思考内容</thinking>
        <tool_name>
            <param1>value1</param1>
        </tool_name>
        ```

        :param xml_content: XML字符串内容
        :return: 包含thinking和tool信息的字典
        """
        import re

        # 清理XML内容
        xml_content = xml_content.strip()

        # 先用正则匹配action标签内容
        action_pattern = re.compile(
            r"(?:<\?xml[^>]*>\s*)?<action>(.*?)</action>", re.DOTALL
        )
        match = action_pattern.search(xml_content)
        if match:
            # 提取action标签内容
            xml_content = f"<action>{match.group(1)}</action>"
        else:
            # 如何没有匹配到action，就用这些内容组装一个action，包含thinking和tool，tool为final_answer
            xml_content = f"""<action>
                <thinking><![CDATA[{query if not query else ""}]]></thinking>
                <final_answer><![CDATA[{xml_content}]]></final_answer>
            </action>"""

        logger.info(f"待解析XML内容: \n {xml_content}")
        
        # 转义XML中的特殊字符&（不在已知XML实体中的&字符）
        # 已知的XML实体: &amp; &lt; &gt; &quot; &apos;
        def escape_ampersands(text):
            # 正则表达式匹配不属于已知XML实体的&字符
            pattern = r'&(?!(amp|lt|gt|quot|apos);)'
            return re.sub(pattern, '&amp;', text)
        
        # 对XML内容进行转义处理
        xml_content = escape_ampersands(xml_content)
        
        # 尝试解析XML
        try:
            root = etree.fromstring(xml_content)
        except etree.XMLSyntaxError as e:
            raise ValueError(f"XML格式错误: {str(e)}")

        # 查找action标签
        action_node = self.find_action_node(root)
        if action_node is None:
            raise ValueError("XML中未找到action标签")

        result = {"thinking": "", "tool": None}

        # 解析thinking节点
        thinking_node = action_node.find("thinking")
        if thinking_node is not None:
            result["thinking"] = (
                thinking_node.text.strip() if thinking_node.text else ""
            )

        # 解析工具节点（第一个非thinking子节点）
        tool_node = None
        for child in action_node:
            if child.tag != "thinking":
                tool_node = child
                break

        if tool_node is not None:
            tool_name = tool_node.tag
            if tool_name == "final_answer":
                result["tool"] = {
                    "name": tool_name,
                    "params": tool_node.text.strip() if tool_node.text else "",
                }
            else:
                result["tool"] = {
                    "name": tool_name,
                    "params": self.parse_nested_params(tool_node),
                }

        return result
