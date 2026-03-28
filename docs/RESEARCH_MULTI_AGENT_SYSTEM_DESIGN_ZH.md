# 基于 nanobot 的科研动态多智能体系统设计（精简版）

本方案在不修改 `nanobot` 核心代码的前提下，基于现有 `tools + skills + spawn` 落地科研协作。核心约束：不新增编排内核，不改 `AgentLoop/Runner/SubagentManager/SessionManager`；Worker 不交换完整报告，只共享结构化关键信息；Reviewer 必须按验收标准用工具核查，不通过则打回。

系统采用“Planner + Implementer + 多 Worker + Reviewer”协作：Planner 负责检索并产出 `candidates.json`、`acceptance_spec.json`；Implementer 负责并行拉起 Worker、汇总黑板、推进轮次；Worker 各自实现一个候选方案；Reviewer 对最终交付做可复现审查。

信息空间分为私有与公共两层。私有层保存完整代码、日志、报告和失败分析；公共层以 `shared/worker_board.json` 记录协作最小必要信息：核心假设、关键改动、指标、优劣、可迁移洞见、下一步动作和私有报告路径，用于跨候选比较与聚合。

Worker 间讨论采用结构化 peer feedback，而非自由聊天。每轮需对其他候选给出 `observed_strengths / observed_weaknesses / borrowable_ideas / suggested_improvement`，并在下一轮明确“采纳了什么、拒绝了什么、原因及效果”，保证讨论可追踪、可落地。

流程推进依赖“黑板 + `agenda.json`”，而非状态机。议程只描述当前轮次、活跃候选、优先问题、下一步动作和送审条件，可随结果动态调整，支持异步推进与打回续跑。默认三轮：第1轮暴露强弱项，第2轮借鉴修复，第3轮收敛到最优或融合方案。

当前系统已具备：run 初始化、自动生成候选、并行 worker 进程编排、三轮协作闭环、结构化同行反馈、全局聚合、动态议程、工具化评审与打回循环，以及最终结论工件自动生成。

结论：该方案本质是“协议层设计”而非“内核重构”。以 Skills 固化角色行为，以共享工件承载协作协议，以工具化验收形成闭环，在现有架构内实现可扩展、可复盘的动态多智能体系统。
