import os
import json
import redis
from datetime import datetime
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

def get_redis_connection():
    """获取 Redis 连接"""
    redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    return redis.from_url(redis_url)

def migrate_knowledge_base_author():
    """
    迁移知识库数据，为没有作者信息的条目添加 'anonymous' 作者。
    """
    redis_conn = get_redis_connection()
    
    # 查找所有用户的知识库队列键
    # 假设用户键的模式是 user:*:knowledge_base:queue
    user_queue_keys = redis_conn.keys("user:*:knowledge_base:queue")
    
    print(f"找到 {len(user_queue_keys)} 个知识库队列键进行迁移。")
    
    for queue_key in user_queue_keys:
        user_name_start_index = queue_key.find(b"user:") + len(b"user:")
        user_name_end_index = queue_key.find(b":knowledge_base:queue")
        user_name = queue_key[user_name_start_index:user_name_end_index].decode('utf-8')
        
        print(f"\n正在处理用户: {user_name}")
        
        knowledge_base_map_key = f"user:{user_name}:knowledge_base:map"
        
        # 获取该用户的所有知识库条目 ID
        item_ids = redis_conn.hkeys(knowledge_base_map_key)
        
        if not item_ids:
            print(f"用户 {user_name} 没有知识库条目。")
            continue
            
        print(f"用户 {user_name} 共有 {len(item_ids)} 个知识库条目。")
        
        for item_id_bytes in item_ids:
            item_id = item_id_bytes.decode('utf-8')
            item_raw = redis_conn.hget(knowledge_base_map_key, item_id)
            
            if item_raw:
                item_data = json.loads(item_raw)
                
                if "author" not in item_data:
                    item_data["author"] = "anonymous"
                    item_data["updated_at"] = datetime.now().isoformat() # 更新时间戳
                    
                    # 更新 map 中的数据
                    redis_conn.hset(
                        knowledge_base_map_key,
                        item_id,
                        json.dumps(item_data, ensure_ascii=False)
                    )
                    
                    # 同时更新 queue 中的数据 (需要找到并替换)
                    # 由于 Redis 列表不支持直接修改元素，需要先删除再添加
                    # 遍历队列，找到对应的 item_id，更新后重新插入
                    queue_items_raw = redis_conn.lrange(queue_key, 0, -1)
                    updated_queue_list = []
                    found_in_queue = False
                    for q_item_raw in queue_items_raw:
                        q_item_data = json.loads(q_item_raw)
                        if q_item_data.get("id") == item_id:
                            q_item_data["author"] = "anonymous"
                            q_item_data["updated_at"] = datetime.now().isoformat()
                            updated_queue_list.append(json.dumps(q_item_data, ensure_ascii=False))
                            found_in_queue = True
                        else:
                            updated_queue_list.append(q_item_raw.decode('utf-8'))
                    
                    if found_in_queue:
                        # 清空旧队列并写入新队列
                        redis_conn.delete(queue_key)
                        if updated_queue_list:
                            redis_conn.rpush(queue_key, *updated_queue_list)
                        print(f"  - 条目 {item_id} (标题: {item_data.get('title', '无标题')}) 已添加作者 'anonymous' 并更新队列。")
                    else:
                        print(f"  - 警告: 条目 {item_id} 在 map 中找到但在 queue 中未找到，仅更新 map。")
                else:
                    print(f"  - 条目 {item_id} (标题: {item_data.get('title', '无标题')}) 已有作者 {item_data['author']}，跳过。")
            else:
                print(f"  - 警告: 无法获取条目 {item_id} 的内容。")
                
    print("\n知识库作者信息迁移完成。")

if __name__ == "__main__":
    migrate_knowledge_base_author()