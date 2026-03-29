# Key Hypothesis
通过低成本排序先筛选候选计划，可快速获得可执行研究方案。

# Implementation Delta
- 生成4份研究草案并执行轻量打分。
- 仅保留前2个草案进入实现环节。
- 增加成本预算阈值控制。

# Strengths
- 迭代速度快。
- 资源消耗可控。

# Weaknesses
- 证据链相对薄弱。
- 排序器对边界案例不稳定。

# Transferable Insights
- 成本阈值机制可用于全局调度。
- 快速草案筛选适合早期探索。

# Open Problems
- 排序器鲁棒性不足。
- 难以识别隐性高价值方案。

# Proposed Next Move
- 引入证据特征到排序器。
- 对边界样本进行对抗评测。
