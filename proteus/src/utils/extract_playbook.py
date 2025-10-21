import re


class PlaybookExtractor:
    @staticmethod
    def extract_tasks_and_completion(playbook_content):
        # 支持两种标题格式：
        # 1. "## 任务规划与完成度"
        # 2. "## 第一部分：任务规划与完成度 (Task Plan & Progress)"
        # 提取从包含"任务规划与完成度"的二级标题开始，到下一个二级标题之间的内容
        tasks_section_pattern = re.compile(
            r"##\s+(?:第[一二三四五六七八九十]+部分：)?.*任务规划与完成度.*?\n(.*?)(?=\n##\s+|\Z)",
            re.DOTALL
        )
        match = tasks_section_pattern.search(playbook_content)

        if match:
            tasks_content = match.group(1)
            task_lines = tasks_content.strip().split("\n")

            extracted_tasks = []
            # 支持两种任务格式：
            # 1. "- [x] 任务描述" 或 "- [ ] 任务描述" 或 "- [-] 任务描述"
            # 2. "1. [x] 任务描述" 或 "1. [ ] 任务描述" 或 "1. [-] 任务描述"
            # 状态说明：[x] = 已完成, [ ] = 未完成, [-] = 进行中
            task_pattern = re.compile(r"^\s*(?:-|\d+\.)\s*\[(x| |-)\]\s*(.*)")
            for line in task_lines:
                task_match = task_pattern.match(line)
                if task_match:
                    status_char = task_match.group(1)
                    if status_char == "x":
                        status = "已完成"
                    elif status_char == "-":
                        status = "进行中"
                    else:
                        status = "未完成"
                    description = task_match.group(2).strip()
                    extracted_tasks.append(
                        {"status": status, "description": description}
                    )
            return extracted_tasks
        return []
