import re


class PlaybookExtractor:
    def extract_tasks_and_completion(playbook_content):
        tasks_section_pattern = re.compile(
            r"##\s+\d+\.\s+任务规划与完成度\s*\n(.*?)(?=\n##|\Z)", re.DOTALL
        )
        match = tasks_section_pattern.search(playbook_content)

        if match:
            tasks_content = match.group(1)
            task_lines = tasks_content.strip().split("\n")

            extracted_tasks = []
            for line in task_lines:
                task_pattern = re.compile(r"-\s*\[(x| )\]\s*(.*)")
                task_match = task_pattern.match(line)
                if task_match:
                    status = "已完成" if task_match.group(1) == "x" else "未完成"
                    description = task_match.group(2).strip()
                    extracted_tasks.append(
                        {"status": status, "description": description}
                    )
            return extracted_tasks
        return []
