# 需求與問題搜集：類似工具與社群回饋（2026-11）

目的：找出網路上與 swimlane-builder 相近的 repo、工具與社群討論中反覆出現的需求和痛點，
對照本專案現況，整理出可以補的缺口。

## 1. 類似的 repo 與工具

| 工具 | 做法 | 跟本專案的差別 |
|---|---|---|
| [jgraph/drawio-mcp](https://cdn.jsdelivr.net/gh/jgraph/drawio-mcp@main/README.md)（官方） | LLM 直接寫 mxGraph XML，事後可選 ELK 重排或 libavoid 重繞線 | 版面仍靠 LLM 或通用演算法，不保證泳道與欄位語意，也不保證每次結果相同 |
| [lgazo/drawio-mcp-server](https://mcpservers.org/servers/lgazo/drawio-mcp-server)、[drawio-mcp (PyPI)](https://pypi.org/project/drawio-mcp/) 等社群 MCP | 透過 MCP 在 draw.io 裡新增圖形，有些附 "polish" 指令修重疊 | 屬「邊畫邊修」，沒有流程本身的檢查 |
| [github/awesome-copilot draw-io-diagram-generator](https://skills.browseract.com/skills/github-awesome-copilot-draw-io-diagram-generator) | Copilot skill，教模型寫 .drawio XML | 同上，版面靠模型 |
| [thechandanbhagat/diagram-master](https://github.com/thechandanbhagat/diagram-master) | MCP，吃 steps/connections JSON 產 draw.io 流程圖 | 結構化輸入的概念最接近，但沒有泳道與流程檢查 |
| [vishalc412/architecture-claudeskill](https://github.com/vishalc412/architecture-claudeskill) | Claude Skill，含 swimlane 類型 | 版面靠模型產生 |
| [ai-solutions-kk/drawio-ai-copilot](https://github.com/ai-solutions-kk/drawio-ai-copilot) | 改版 draw.io Desktop，內建 AI 產圖與自動排版 | 要裝改版桌面程式和 API key |
| [stieges/bpmn-generator](https://github.com/stieges/bpmn-generator) | 自然語言或 JSON → BPMN 2.0 XML + SVG，支援多 pool 與 lanes | 目標是 BPMN 標準，不是 draw.io |
| Eraser、Lucid、Miro、Taskade、Creately、ClickUp 等 SaaS | 用 prompt 或文件生成泳道圖 | 要帳號、資料會上傳、結果不可重現 |
| Mermaid / PlantUML | 圖即程式碼 | 沒有原生泳道，或泳道配上迴圈有問題（見下節） |

## 2. 社群反覆提到的問題

### A. 「圖即程式碼」工具沒有好用的泳道
- Mermaid 沒有原生泳道。用 subgraph 硬做，泳道對不齊、寬度不一致。
  [Mermaid-Chart #128](https://github.com/Mermaid-Chart/issue-tracker/issues/128)；
  mermaid-js 上更早的同類需求約有 106 個讚、39 則留言（[鏡像](https://lightrun.com/answers/mermaid-js-mermaid-use-swimlanes-in-flowchart-diagram)）；
  中文社群也有同樣抱怨（[iT 邦](https://ithelp.ithome.com.tw/articles/10384366)）。
- PlantUML 的 `goto` 還是實驗功能，跟 swimlane 一起用會失效；往回跑的迴圈線落在錯的泳道或錯的一側。
  （[goto + swimlanes](https://forum.plantuml.net/16520/label-processing-label-together-swimlanes-activity-diagram)、
  [backward loop side](https://forum.plantuml.net/13006/ability-change-backward-especially-swimlanes-activity-diagram)、
  [官方 beta 文件](https://plantuml.com/activity-diagram-beta)）

**對照本專案：** 本專案已經解決。`"kind": "feedback"` 迴圈和「go to step N」都是一級概念，值得在 README 寫明。

### B. LLM 直接畫流程圖不可靠
- 圖形重疊、連線交叉、間距不一致；同樣輸入每次產出不同；會漏步驟、邏輯不一致；
  遇到模糊的地方不會發問，而是自己猜。
  （[SocietyByte 2026-02](https://www.societybyte.swiss/en/2026/02/12/why-ai-cant-yet-generate-business-process-diagrams/)、
  [MAO 論文](https://arxiv.org/abs/2408.01916)、
  [LLM 製模 copilot 使用者研究](https://arxiv.org/pdf/2603.12895)）
- 業界的解法是加上驗證與自動修復（[SocietyByte 2026-05](https://www.societybyte.swiss/en/2026/05/21/intelligent-process-decomposition-a-pragmatic-approach-to-bpmn-generation/)）。

**對照本專案：** 版面確定、結果可重現、有 lint、會標出不清楚的地方，這些已經涵蓋。
**仍有缺口：** 沒有檢查「SOP 原文的每一步都出現在圖裡」，可以做步驟覆蓋率或對照表（見需求 R4）。

### C. 改一步就要重排整張圖
- 「每次小改都要把其他東西搬一遍」（[StackExchange](https://webapps.stackexchange.com/questions/39132/in-draw-io-is-there-a-way-to-automatically-position-a-swimlane-or-process-diagr)）。
- 調整泳道大小時，手工排好的連線跟著跑掉（[jBPM](https://issues.redhat.com/browse/RHBPMS-2039)、[Syncfusion](https://www.syncfusion.com/feedback/12802/node-dragging-in-swimlane-is-not-working-properly-when-line-routing-is-enabled)）。

**對照本專案：** 這正是本專案的核心價值。
**反面需求：** 也有人想在生成後微調。本專案目前會讓手動修改失效（見需求 R6）。

### D. 缺少「階段 / Phase」這個維度
- draw.io [#3551](https://github.com/jgraph/drawio/issues/3551)：想同時用「部門分工」和「階段」兩個維度呈現流程，
  只能手動拼湊，泳道一調整就要修很多元件。
- Lucid 使用者想要「上方用直欄表示流程生命週期、下方是角色泳道」，AI 做不到
  （[Lucid 社群](https://community.lucid.co/ideas/use-ai-to-generate-flowcharts-with-swimlanes-7421)）。

**對照本專案：** schema 目前只有 `meta / lanes / nodes / edges`，沒有 phase。**這是明確的缺口。**

### E. 泳道方向
- Lucid AI 被要求畫直向泳道，卻一直產出橫向（同上 Lucid 討論）。

**對照本專案：** 目前只有橫向泳道。

### F. 寬流程、大流程
- 本專案在 14 欄以上會發出警告（W202 / W209），但分割要使用者自己來。
- BPMN 的 auto-layout 工具會直接丟掉多 pool 與跨 pool 的訊息流
  （[bpmn-auto-layout README](https://cdn.jsdelivr.net/npm/bpmn-auto-layout@1.3.0/README.md)、
  [forum.bpmn.io](https://forum.bpmn.io/t/problem-with-bpmn-auto-layout/5016)），
  社群因此另外做了 [bpmn-generator](https://github.com/stieges/bpmn-generator)。

### G. 從 Excel / 流程表格生成圖的工具正在消失
- Microsoft 已退役 Excel 的 Visio Data Visualizer 增益集，改成只有 Visio Plan 2 能用
  （[Microsoft 公告](https://techcommunity.microsoft.com/t5/microsoft-365-blog/retirement-of-the-visio-data-visualizer-add-in-for-excel-and/ba-p/4465747)）。
  原本「Excel 流程表 → 跨部門流程圖」的免費路線沒了。
- Visio 社群也有人想把 RACI 嵌進跨部門流程圖
  （[techcommunity](https://techcommunity.microsoft.com/t5/visio/cross-functional-flowcharts-with-embedded-raci/td-p/1361975)）。

### H. 通用自動排版處理不了泳道
- ELK 的 partitioning 會影響邊的方向與分層，泳道內的順序可能被交叉最小化打亂
  （[ELK 文件](https://eclipse.dev/elk/blog/posts/2023/23-01-09-constraining-the-model.html)）。
  官方 draw.io MCP 的事後排版就是依賴這類演算法。

**對照本專案：** 這正好是本專案和官方 MCP 的差異化，可以拿來當宣傳重點。

## 3. 整理出的需求清單（建議優先度）

| # | 需求 | 依據 | 現況 | 建議 |
|---|---|---|---|---|
| R1 | **階段 / Phase 欄**（第二維度：欄位帶狀標題） | D | 沒有 | **高**：需求明確，且本專案的欄位計算剛好可以支撐 |
| R2 | **Excel / CSV 流程表直接輸入**（不經 AI，或 AI 只補缺） | G | 只有 .docx / 文字輸入 | **高**：承接 Visio Data Visualizer 的使用者 |
| R3 | **README 寫明跟 Mermaid / PlantUML / draw.io MCP 的差異** | A、B、H | README 沒有比較 | **高**：成本低，SEO 與說服力都有幫助 |
| R4 | **SOP 原文 ↔ 圖的步驟覆蓋檢查**（漏步驟、多出來的步驟） | B | lint 只檢查結構 | 中 |
| R5 | **大流程分頁**：子流程、跨頁連接點，自動切成多頁 | F | 只發警告 | 中 |
| R6 | **保留部分手動調整**（例如鎖定欄位、覆寫順序） | C 反面 | `col` 只能當下限 | 中，要小心別破壞「結果可重現」 |
| R7 | **直向泳道** | E | 沒有 | 低到中 |
| R8 | **RACI 或其他角色資訊**（A/C/I 的標記） | G | 沒有 | 低 |
| R9 | **匯出其他格式**：BPMN XML、Mermaid，或 SVG/PNG 預覽 | A、F | 只有 .drawio | 低到中；draw.io 本身就能轉 .vsdx / PDF |

## 4. 限制說明
- Reddit 與 Hacker News 的討論串沒能直接抓到內容，社群聲音主要來自 GitHub issue、PlantUML 論壇、Lucid 與 Microsoft 社群。
- 部分來源是廠商部落格，看法偏主觀；Lightrun 上的讚數與留言數是鏡像資料，沒有回 GitHub 原頁確認。
