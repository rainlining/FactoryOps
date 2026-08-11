# Change 学习计划：2026-08-10-establish-openspec-learning-governance

## 学习元数据

- `learning_level`: `standard`
- `pattern_stage`: `N/A`
- `first_deep_reference`: `N/A`

## 完成后应具备的能力

项目所有者能够：

- 说明 proposal、spec、design、tasks、learning、verification 各自解决什么问题；
- 说明 Change 为什么必须先 review 设计再实现；
- 说明 `technically-verified` 与 `completed` 的区别；
- 说明 Deep Change 的 Learning Gate 为什么不以背诵 API 为核心；
- 判断一个 Change 是否过大；
- 判断重复模式何时可以降级、何时必须重新升级。

## 编码前讲解清单

本 Change 不包含实现代码，因此 Deep 编码前讲解不适用。Review 时需要理解：

- [ ] OpenSpec 主工件及 FactoryOps 扩展工件的责任边界；
- [ ] Change 生命周期和 review 停顿点；
- [ ] Deep/standard/delegated 的差别；
- [ ] 重复工程模式的等级递减条件；
- [ ] Learning Gate 的真实能力验收标准。

## 真实 Code Walkthrough 路线

本 Change 没有运行时代码调用链。文档 Walkthrough 路线为：

1. 从根目录 `AGENTS.md` 查看仓库级约束；
2. 从 `openspec/config.yaml` 查看 OpenSpec 上下文与工件规则；
3. 从 `openspec/README.md` 查看生命周期；
4. 从 `_templates/` 选择新 Change 工件；
5. 在 `changes/<change-id>/` 完成和推进实际 Change；
6. 完成后将规格合入 `openspec/specs/` 并归档。

## 项目所有者亲自修改任务

`N/A`。本 Change 是 standard，没有强制所有者代码修改任务。项目所有者通过 review 中文治理文件完成验收。

## Failure/Debug Exercise

`N/A`。本 Change 不包含运行时失败模型。治理失败场景已经在 design 和 spec 中通过人工一致性检查覆盖。

## Learning Gate

本 Change 使用 Standard Review Gate：

- [x] 已通过 review 确认六类 Change 工件的职责符合后续开发需要。
- [x] 已通过 review 接受 Change 的完整生命周期。
- [x] 已接受重复模式的等级递减及重新升级条件。
- [x] 已 review 中文 `AGENTS.md` 并明确接受。

`gate_status`: `passed`
