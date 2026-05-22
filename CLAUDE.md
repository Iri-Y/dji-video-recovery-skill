# DJI Video Recovery Skill - 使用说明

## 项目结构

```
dji-video-recovery-skill/
├── README.md                    # 中英文文档（GitHub 首页）
├── skill.md                     # AI 技能定义（skill 核心文件）
├── scripts/
│   ├── fat_chain_recover.py     # 核心恢复脚本
│   └── verify_recovery.py       # 批量验证脚本
└── install.sh                   # 安装脚本
```

## 安装到 Claude Code

```bash
./install.sh
```

这会将 `skill.md` 安装到 `~/.claude/skills/dji-video-recovery.md`，并将脚本安装到 `~/.claude/scripts/`。

## 安装到其他 AI 工具

将 `skill.md` 的内容添加到你使用的 AI 工具的指令集或项目配置中。

## 使用

安装后，只需告诉 AI：

> "我的 DJI 无人机 SD 卡有误删的视频需要恢复。SD 卡在 /Volumes/SD_Card。"

AI 会自动按照 skill.md 中定义的工作流执行恢复。
