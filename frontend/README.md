# 足球数据分析前端

## 快速启动

```bash
# 安装依赖
npm install

# 启动开发服务器
npm run dev
```

## 项目结构

```
frontend/
├── public/              # 静态资源
├── src/
│   ├── api/            # API调用
│   ├── components/     # 组件
│   ├── pages/          # 页面
│   ├── App.vue         # 根组件
│   └── main.js         # 入口文件
├── index.html          # HTML模板
├── package.json        # 项目配置
└── vite.config.js     # Vite配置
```

## 页面说明

- **首页**: 今日比赛、即将开始的比赛、联赛列表、FIFA排名
- **联赛页**: 积分榜、比赛列表
- **球队页**: 球队信息、近期状态、赛程密集度、历史战绩
- **分析页**: 球队搜索、交锋分析