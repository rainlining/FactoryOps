# Verification

状态：`review-handoff-ready`。

- `/api/scenario`：HTTP 200；`/api/inspection-image`：HTTP 200、`image/png`、约 3.16MB。
- 路径穿越和 query 变体返回 404；`node --check`、Python compile、`git diff --check` 通过；dataset 未修改。
- 独立复审：0 Critical / 0 Important；场景 run_id 和固定图片 endpoint provenance 校验已补齐。
- 非阻塞 Minor：API fallback 不加载 recorded inspection；场景文件暂未带内容 hash。
