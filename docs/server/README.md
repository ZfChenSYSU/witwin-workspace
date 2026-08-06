# 当前服务器工程文档

本目录是服务器端无 LiDAR SLAM 环境、重建流水线和运行验证文档的 Git 唯一编辑入口。
以后新增或更新工程文档，应直接在本目录完成，不再把
`/root/nfs/chenzhf/witwin/docs` 作为文档源。

## 文档索引

- `WORKING_DIRECTORY_GUIDE.md`：每类任务应使用的工作目录。
- `REMOTE_AGENT_OPERATIONS_2026-08-06.md`：远程连接、环境入口、安全边界和 Agent 操作顺序。
- `COLMAP_CAPABILITY_BOUNDARY_2026-08-06.md`：当前已验证能力、未验证能力和使用限制。
- `IPHONE_SESSION_IMPORT_REQUIREMENTS_2026-08-06.md`：iPhone 数据契约、导入分析和验收要求。
- `NO_LIDAR_SLAM_SERVER_ENVIRONMENT_PLAN_2026-08-05.md`：环境与技术路线计划。
- `NO_LIDAR_SLAM_SERVER_INSTALL_RECORD_2026-08-05.md`：实际安装记录。
- `SOUTH_BUILDING_RECONSTRUCTION_TEST_2026-08-06.md`：端到端重建测试记录。
- `DEPLOYMENT_REQUEST_2026-08-05.md`：初始部署需求与安全边界存档。

计划、安装、测试和部署需求文档由原位置复制而来，原文件没有删除；索引、目录规范、
能力边界和导入需求是在 Git worktree 中新增的交接文档。自本次整理后，Git 目录中的
版本是后续修改和提交的规范版本；外部副本只作为历史留存。
