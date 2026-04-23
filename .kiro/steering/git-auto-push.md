---
inclusion: always
---

# Git 自动提交规则

每次完成所有文件修改后（不是每改一个文件就提交），主动执行：

```
git add -A && git commit -m '用中文简要描述本次修改内容' && git push origin main && git push gitlab main
```

要求：
- commit message 用中文，具体描述改了什么
- 所有修改完成后统一提交一次，不要每改一个文件就提交
- 如果本次对话没有修改任何文件，不需要执行 git 操作
- 推送到 origin（GitHub）和 gitlab 两个远程仓库
