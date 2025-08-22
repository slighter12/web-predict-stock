# Web Predict Stock

股票預測網頁應用程式

## 安全性更新 (2024)

本專案已進行全面的安全性更新，包括：

### 主要更新
- ✅ 更新 Node.js 版本要求到 18.19.0+
- ✅ 替換已棄用的 `request` 套件為 `axios`
- ✅ 替換已棄用的 `sqlite3` 套件為 JSON 文件存儲
- ✅ 替換已棄用的 `node-sass` 套件為 `sass`
- ✅ 更新所有依賴到安全版本
- ✅ 更新 Webpack 配置到版本 5
- ✅ 保留並更新 Pug 模板支持

### 修復的安全漏洞
- 修復了 111 個安全漏洞
- 包括 7 個低風險、49 個中風險、40 個高風險和 15 個關鍵風險
- 移除了惡意軟體風險的 `fsevents` 套件

## 系統需求

- Node.js 18.19.0 或更高版本
- npm 8.0.0 或更高版本

## 安裝

```bash
# 使用 nvm 切換到正確的 Node.js 版本
nvm use

# 安裝依賴
npm install
```

## 開發

```bash
# 開發模式
npm run dev

# 啟動開發伺服器
npm run start:dev
```

## 建置

```bash
# 生產建置
npm run build

# 啟動生產伺服器
npm start
```

## 專案結構

```
web-predict-stock/
├── app/                    # 應用程式邏輯
│   ├── getStockList.js    # 獲取股票列表
│   ├── getStockHistory.js # 獲取股票歷史數據
│   ├── insertdb.js        # 資料庫插入
│   ├── preprocessStockData.js # 股票數據預處理
│   └── proxy_pool.js      # 代理池 (使用JSON存儲)
├── src/                   # 前端源碼
│   ├── index.js          # 主要 JavaScript
│   ├── index.pug         # Pug 模板 (已更新)
│   └── app.sass          # Sass 樣式
├── server.js             # Express 伺服器
├── webpack.config.js     # Webpack 配置
└── package.json          # 專案依賴
```

## 注意事項

- 本專案使用 MongoDB 作為主要資料庫
- 代理數據使用 JSON 文件存儲，避免複雜的資料庫依賴
- 所有 HTTP 請求現在使用 axios 而非已棄用的 request 套件
- 使用 Pug 模板引擎，提供更好的開發體驗
