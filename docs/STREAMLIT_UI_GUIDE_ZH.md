# Streamlit 本地可视化测试台

本文档描述如何使用 `apps/research_flow_ui.py` 对 `research_nanobot` 的完整协议流程进行可视化测试。

## 目标

该 UI 面向本项目的协议链路验证，覆盖：

1. 初始化 run
2. 从私有报告提取摘要
3. 写入公共黑板
4. 合并 peer feedback
5. 校验黑板
6. 聚合全局发现
7. 生成下一轮动态议程
8. 生成最终结论（JSON + Markdown）

## 安装

在仓库根目录执行：

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -U pip
pip install -e .[ui]
```

如果你已经安装过项目，仅需补装 UI 依赖：

```bash
pip install streamlit
```

## 启动

```bash
streamlit run apps/research_flow_ui.py
```

启动后浏览器会打开本地页面（默认 `http://localhost:8501`）。

## 页面结构

UI 包含 5 个页签：

1. `一键全流程`
2. `分步执行`
3. `结果可视化`
4. `结论`
5. `帮助`

## 推荐测试方式

### 方式 A：一键全流程

1. 在左侧 `运行配置` 中确认路径：
   - `Candidates File`
   - `Acceptance File`
   - `Reports Dir`
   - `Feedback Dir`
2. 在 `一键全流程` 点击 `运行完整流程`
   - 该按钮调用后端脚本 `nanobot/skills/research-implementer/scripts/run_full_cycle.py`
3. 切换到 `结果可视化` 查看：
   - `worker_board.json`
   - `agenda.json`
4. 重点确认：
   - `agenda.round_index` 变为 `2`
   - `active_candidates` 非空
   - `priority_questions` 非空
5. 在 `结论` 页签确认：
   - `final_conclusion.json` 已生成
   - `final_conclusion.md` 已生成

### 方式 B：分步调试

按页面顺序点击：

1. `初始化`
2. `生成摘要并写入黑板`
3. `合并所选反馈`
4. `校验黑板`
5. `聚合全局发现`
6. `生成下一轮议程`
7. `生成结论文件`

该模式适合定位某一步的结构问题。

## 输入文件命名约定

UI 在自动流程中使用以下命名规则：

- 报告：`<candidate_id>_round_<round>_report.md`
- 指标：`<candidate_id>_round_<round>_metrics.json`
- 反馈：`<from_candidate>_on_<to_candidate>.json`

默认示例在：

- `examples/research-demo/reports/`
- `examples/research-demo/feedback/`
- `examples/research-demo/review/`

## 注意事项

1. 共享黑板 `worker_board.json` 目前按顺序写入，避免并发写同一文件。
2. Worker 之间应只通过摘要和反馈 JSON 交换关键信息，不直接共享完整报告。
3. 若接入真实实验数据，保持 digest 和 feedback 的字段结构不变。
4. 若要输出可交付结论，建议提供 reviewer feedback（`approved/must_fix/evidence`）。
