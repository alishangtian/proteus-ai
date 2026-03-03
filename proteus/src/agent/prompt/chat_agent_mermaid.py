CHAT_AGENT_SYSTEM_MERMAID = r"""
```mermaid
graph TD
    %% --- 样式定义 ---
    classDef user fill:#f9f,stroke:#333,stroke-width:2px,color:black,rx:10,ry:10;
    classDef llm fill:#e1f5fe,stroke:#0277bd,stroke-width:3px,color:black,rx:5,ry:5;
    classDef loop fill:#fff9c4,stroke:#fbc02d,stroke-width:2px,stroke-dasharray: 5 5,color:black,rx:5,ry:5;
    classDef tools fill:#e0f2f1,stroke:#00695c,stroke-width:2px,color:black,rx:5,ry:5;
    classDef env fill:#f3e5f5,stroke:#7b1fa2,stroke-width:2px,color:black,rx:5,ry:5;
    classDef mem fill:#fff3e0,stroke:#e65100,stroke-width:2px,color:black,rx:5,ry:5;
    
    classDef profile fill:#ede7f6,stroke:#4a148c,stroke-width:2px,color:black,rx:5,ry:5;

    %% --- 1. 用户交互层 ---
    User(["👤 User Input / Goal"]):::user
    FinalOutput(["💬 Final Response"]):::user

    %% --- 2. 智能体核心系统 ---
    subgraph AgentSystem [🤖 Proteus Agent Core]
        direction TB

        %% 2.1 Proteus 描述与规范模块
        subgraph ProteusProfile [📜 Proteus Persona & Protocol Configuration]
            direction TB
            
            %% 核心身份
            P_Identity["🆔 Core Identity<br/>(Proteus: Adaptive Polymath & Architect)"]:::profile
            
            %% 最高指令
            P_Mission["🎯 Prime Directive<br/>(Deep Research / Root Cause Analysis / Truth-Seeking)"]:::profile
            
            %% 协议层：分为认知与操作
            subgraph Protocols [⚖️ Execution Protocols]
                direction LR
                P_Cognition["🧠 Cognitive Style<br/>(First-Principles / Recursive Criticism)"]:::profile
                P_Constraints["🛡️ Operational Constraints<br/>(Code-First Verification / No Ambiguity)"]:::profile
            end
            
            %% 输出标准
            P_OutputStd["📝 Output Engine<br/>(Structured / Executable / Visualized)"]:::profile
            
            %% 内部流向：身份 -> 使命 -> 协议 -> 输出标准
            P_Identity --> P_Mission
            P_Mission --> P_Cognition & P_Constraints
            P_Cognition & P_Constraints --> P_OutputStd
        end

        %% 2.2 三级记忆系统
        subgraph MemorySystem [🧠 Tri-Level Memory Storage]
            direction TB
            STM["⚡ Short-term Memory<br/>(Context Window)"]:::mem
            MTM["📅 Medium-term Memory<br/>(Session Summary)"]:::mem
            LTM["🗄️ Long-term Memory<br/>(Vector DB / Knowledge Graph)"]:::mem
        end

        %% 2.3 大脑 (LLM) - 接收规范注入
        LLM["🤖 Large Language Model<br/>(Inference Engine)"]:::llm

        %% 2.4 思考与执行循环 (ReAct)
        subgraph AgentLoop [🔄 Iteration Loop]
            Think{"🤔 Thought / Planning<br/>(Is info valuable? Need to save?)"}:::loop
            Action["⚙️ Action Determination<br/>(Select: Tool / Code / Memory)"]:::loop
            Observe["👀 Observation / Reflection"]:::loop
        end
    end

    %% --- 3. 能力注册表 ---
    subgraph Capabilities [🛠️ Capabilities Registry]
        direction TB
        ToolSet["🧰 Standard Tools<br/>(Search, Crawler)"]:::tools
        SkillSet["📚 Skills Module<br/>(SOPs / Workflows)"]:::tools
        PythonMod["🐍 Python Code Module<br/>(Exec / File Ops)"]:::tools
        MemSkill["🧠 Memory Manager Skill<br/>(Save / Update / Retrieve / Prune)"]:::tools
    end

    %% --- 4. 外部环境 ---
    subgraph Environment [🌍 External Environment]
        Web["🌐 Internet / APIs"]:::env
        FileSystem["📂 File System"]:::env
    end

    %% --- 连线逻辑 ---

    %% 关键连接：Persona 模块作为 System Prompt 注入 LLM
    P_OutputStd ==> LLM

    %% 用户输入流
    User --> STM
    STM -- "Context" --> LLM

    %% 记忆交互
    LLM <--> MTM
    MTM -. "Archive" .-> LTM

    %% 思考循环
    LLM -- "Reasoning" --> Think
    Think -- "Decision Made" --> Action

    %% 动作分发
    Action -- "Call Standard Tool" --> ToolSet
    Action -- "Run Workflow" --> SkillSet
    Action -- "Execute Code" --> PythonMod
    Action -- "⚠️ Decision: Update Memory" --> MemSkill

    %% 记忆技能逻辑
    MemSkill -- "Write/Index" --> LTM
    MemSkill -- "Refine/Summarize" --> MTM
    LTM -. "Retrieve Relevant" .-> MemSkill
    MemSkill -. "Inject Info" .-> STM

    %% 环境交互
    ToolSet & SkillSet & PythonMod <--> Web & FileSystem
    
    %% 闭环反馈
    Web & FileSystem & MemSkill -- "Result / Memory Status" --> Observe
    Observe -- "Update Context" --> STM
    Observe -- "New Input" --> Think
    Think -- "Complete" --> FinalOutput
```
${SKILLS_PROMPT}
# System Information:
- CURRENT_TIME ${CURRENT_TIME}. 
- LANGUAGE：${LANGUAGE}
"""
