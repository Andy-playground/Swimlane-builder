# 需求與問題搜集：類似工具、GitHub 與社群回饋（2026-11）

目的：找出網路上與 swimlane-builder 相近的 repo、工具與社群討論中反覆出現的需求和痛點，
對照本專案現況，整理出可以補的缺口。

第二版加入 GitHub：用 GitHub 搜尋 API 找相近的 repo，並讀了 Mermaid、draw.io、
bpmn-auto-layout、ProcessPiper 等專案的 issue 與 PR。數字是 2026-11-14 的查詢結果。

> **更正第一版：** 第一版說「Mermaid 沒有原生泳道」，這已經過時。Mermaid 從 11.16.0 起有
> `swimlane-beta`，詳見 §2。

## 0. 重點摘要

1. **最大的變數是 Mermaid `swimlane-beta`。** 社群等了五年的需求（[#2028](https://github.com/mermaid-js/mermaid/issues/2028)，
   401 個讚、128 則留言）在 2026-06 結案，現在正在密集修版面問題；階段（phase）的 PR 也已經送出。
2. **「AI 理解流程，程式負責版面」不再是獨家做法。** 2026 年下半年至少出現 5 個同樣主打這點的 repo，
   有些已經做了本專案還沒有的功能：階段帶、直向泳道、保留手動修改、RACI。
3. **本專案真正的差異在品質細節：** 逐位元組相同的輸出、可讀性預算（W209）、標籤擺放、
   事後檢查流程本身。這些需要在 README 講清楚，並跟競品做比較。
4. **用戶最常要的功能：** 階段（第二維度）、生成後還能手動修改又不被下次覆蓋、
   多種方向與輸出格式、長流程的處理。

## 1. 類似的 repo 與工具

### 1.1 直接競品：同樣是「AI 理解語意，程式計算版面」

| Repo | ★ | 建立 | 輸出 | 本專案沒有的功能 |
|---|---|---|---|---|
| [zz-zed/product-swimlane-drawio](https://github.com/zz-zed/product-swimlane-drawio) | 2 | 2026-08 | .drawio | **直向泳道、階段帶、`inspect / patch / compare` 增量更新並保留手動修改**、穩定 ID、輸出 SHA-256 收據；有 Claude 與 Codex 的 plugin marketplace 安裝方式；有中文 README |
| [Castaldo-Solutions/process-builder](https://github.com/Castaldo-Solutions/process-builder) | 13 | 2026-07 | .drawio | **多個階段**、**痛點（pain point）標註**、工具註記、**AS-IS / TO-BE（Quick Win、Full Automation）**、強制先訪談再畫、`--strict` 模式 |
| [mssoftjp/process-model-generator](https://github.com/mssoftjp/process-model-generator) | 0 | 2026-09 | SVG | **橫向與直向兩種方向**、**匯入 BPMN 2.0 XML**、平行與包容閘道、`.flow` 文字中介格式、在 1600×900 畫布上量測可讀性 |
| [younessili/process-flow](https://github.com/younessili/process-flow) | 7 | 2026-08 | Excalidraw → PNG | **角色 × 階段格線**、人工與自動步驟分色、輸出 PNG 後切片讓 AI 再用眼睛檢查 |
| [pohsuntw-lab/EW-AI-Flowchart](https://github.com/pohsuntw-lab/EW-AI-Flowchart)（台灣） | 1 | 2026-09 | EFD JSON → 桌面版 → .drawio、SVG、PNG、PDF | **流程階段、節點層級的 RACI**、文件與證據、例外與升級的閉環檢查；ChatGPT plugin；**中文使用者會直接拿來比較** |
| [ievsantillan/process-swimlanes-drawio](https://github.com/ievsantillan/process-swimlanes-drawio) | 0 | 2026-06 | .drawio | **同一來源產出兩種詳細度**（給主管看的簡版、給專家看的詳版）、依風險分色、交叉引用假設清單 |
| [csgoh/processpiper](https://github.com/csgoh/processpiper) | 204 | 2023-01 | PNG、SVG | 純文字 DSL（PiperFlow）、pool 加 lane；最近一次 push 是 2024-11 |
| [tmiyakawa-tsp/drawio-swimlane-flowchart](https://github.com/tmiyakawa-tsp/drawio-swimlane-flowchart) | 0 | — | .drawio | 日文、直向泳道；做法是讓 AI 直接寫 XML |

### 1.2 間接競品

| 工具 | 做法 | 跟本專案的差別 |
|---|---|---|
| **Mermaid `swimlane-beta`**（11.16.0 起） | 文字 DSL；支援 TB、BT、LR、RL 四種方向；GitHub、GitLab、Notion 等地方能直接顯示 | 免安裝、到處都能顯示；但還在 beta，版面問題很多（§2.1）|
| [jgraph/drawio-mcp](https://github.com/jgraph/drawio-mcp)（官方） | AI 寫 XML，可選擇事後用 ELK 或 libavoid 重排 | 版面靠通用演算法，不懂泳道與欄位的語意 |
| draw.io 社群的 MCP 與 skill（lgazo、awesome-copilot、vibepm666/drawio-generator 等） | AI 直接產生 XML | 同上 |
| [ProMoAI](https://github.com/fit-process-mining/ProMoAI)（78★）、Txt2BPMN、text-to-bpmn2.0 | 自然語言轉成 BPMN 或 POWL 流程模型 | 偏學術與流程探勘，不是做文件用的圖 |
| [nqhaivn/QH-Process-Shorthand](https://github.com/nqhaivn/QH-Process-Shorthand) | 給一般人手寫的流程速記 DSL，含泳道 | 可參考它怎麼寫「go to」與步驟編號 |
| Eraser、Lucid、Miro、Taskade 等 SaaS | prompt 轉圖 | 要帳號、資料會上傳、結果無法重現 |

## 2. GitHub issue 裡的需求與痛點

### 2.1 Mermaid `swimlane-beta`：社群最想要什麼、目前哪裡壞

需求有多大：
- [#2028 Use swimlanes in flowchart diagram](https://github.com/mermaid-js/mermaid/issues/2028)：**401 個讚、128 則留言**，從 2021 年開到 2026-06-02 才結案。
  另有 [#2623 BPMN support](https://github.com/mermaid-js/mermaid/issues/2623)（165 讚，還沒結案）。
- [drawio#5780](https://github.com/jgraph/drawio/issues/5780)：使用者要 draw.io 匯入 Mermaid 泳道，
  因為「轉成流程圖再手動排泳道很花時間」。

用戶回報的問題，可以當成本專案的測試清單：

| Issue | 問題 | 本專案現況 |
|---|---|---|
| [#8327](https://github.com/mermaid-js/mermaid/issues/8327) | 連線加上標籤後，節點跑位、不再對齊 | 版面確定，但值得加一個「加標籤不移動節點」的回歸測試 |
| [#8355](https://github.com/mermaid-js/mermaid/issues/8355) | 同一泳道的節點依 ID 字母排序，不是照原始碼順序 | 本專案依流程順序排，可以寫成賣點 |
| [#8759](https://github.com/mermaid-js/mermaid/issues/8759) | 版面會隨瀏覽器語系改變（`localeCompare`） | 本專案逐位元組相同；值得確認 Python 端也沒有依賴語系的排序 |
| [#7964](https://github.com/mermaid-js/mermaid/issues/7964) | 標題很長、連線很多時完全看不懂 | W201、W209 已涵蓋 |
| [#7830](https://github.com/mermaid-js/mermaid/issues/7830) | 匯出 PNG 和網頁上看到的不一樣 | 本專案只輸出 .drawio，由 draw.io 自己匯出 |
| [#7822](https://github.com/mermaid-js/mermaid/issues/7822) | 拿真實 SOP 畫，跨角色的箭頭要用 `<br>` 硬擠 | 本專案的通道會自動加寬 |
| [#8622](https://github.com/mermaid-js/mermaid/issues/8622)、[#8446](https://github.com/mermaid-js/mermaid/issues/8446) | 自迴圈疊在既有連線上，或直接當掉 | 待確認本專案是否支援自迴圈 |
| [#8760](https://github.com/mermaid-js/mermaid/issues/8760)、[#8781](https://github.com/mermaid-js/mermaid/issues/8781) | 空泳道畫錯 | 待確認本專案怎麼處理空泳道 |
| [#8605](https://github.com/mermaid-js/mermaid/issues/8605)、[PR #8606](https://github.com/mermaid-js/mermaid/pull/8606) | 菱形比周圍節點高很多，想要比較扁的菱形 | 待比對 |
| [#8689](https://github.com/mermaid-js/mermaid/issues/8689) | 決策的短分支應該放在決策旁邊；泳道不要保留空白帶 | 跟 README「已知限制」第 3 點（決策分支交叉）有關 |

正在進行的新功能：
- **[#8386](https://github.com/mermaid-js/mermaid/issues/8386) 和 [PR #8407](https://github.com/mermaid-js/mermaid/pull/8407)：階段，跟泳道交叉的第二個軸。**
  議題裡明說 Visio 的跨部門流程圖本來就有 Phase，BPMN 2.0 反而沒有這個概念，所以 bpmn-beta 補不上。
  另一個常見情境是：全部由同一個團隊做的流程，泳道沒有資訊，結構全在階段上。
- [PR #8313](https://github.com/mermaid-js/mermaid/pull/8313)：「AI-first」的原生 BPMN 圖，可以匯出 BPMN 2.0 XML（已結案）。

### 2.2 draw.io（jgraph/drawio）
- [#3551](https://github.com/jgraph/drawio/issues/3551)、[#3897](https://github.com/jgraph/drawio/issues/3897)：要「部門 × 階段」的交叉泳道；
  現在要手動拼湊，泳道一調整就要搬很多元件。
- [#2956](https://github.com/jgraph/drawio/issues/2956)：匯入 Visio（VSDX）時泳道要完整保留，代表有 Visio 使用者在遷移過來。
- [#4121](https://github.com/jgraph/drawio/issues/4121)、[#520](https://github.com/jgraph/drawio/issues/520)：draw.io 內建的 CSV 匯入，泳道父子關係要匯兩次，連線也會漏。
  有人想用表格產生泳道圖，但內建工具不好用。
- [#5016](https://github.com/jgraph/drawio/issues/5016)、[#5454](https://github.com/jgraph/drawio/issues/5454)：自動排版要尊重使用者手動調整過的順序。
- [#5082](https://github.com/jgraph/drawio/issues/5082)、[#5362](https://github.com/jgraph/drawio/issues/5362)：巢狀泳道的自動排列和方向切換有錯。

### 2.3 bpmn-auto-layout 與 ProcessPiper
- [bpmn-auto-layout#93](https://github.com/bpmn-io/bpmn-auto-layout/issues/93)：連線交叉讓圖難讀，手動排的版本沒有交叉。
- [bpmn-auto-layout#53](https://github.com/bpmn-io/bpmn-auto-layout/issues/53)（10 則留言）：**局部排版**，保留已有的座標，只排新加的部分。
- [processpiper#15](https://github.com/csgoh/processpiper/issues/15)：圖太長時，最後一段被截掉。
- [processpiper#45](https://github.com/csgoh/processpiper/issues/45)：一個節點超過 4 條連線就畫不出來，或者節點重疊。
- [processpiper#46](https://github.com/csgoh/processpiper/issues/46)（20 則留言）、[#13](https://github.com/csgoh/processpiper/issues/13)、[#37](https://github.com/csgoh/processpiper/issues/37)：要 XML、SVG、BPMN 匯出。
- [processpiper#50](https://github.com/csgoh/processpiper/issues/50)：「想拿它教 GPT 畫流程圖」，要更多給 LLM 的範例。

### 2.4 draw.io MCP（jgraph/drawio-mcp）
- 問題多半是安裝與傳輸層的（[#16](https://github.com/jgraph/drawio-mcp/issues/16)、[#34](https://github.com/jgraph/drawio-mcp/issues/34)、[#29](https://github.com/jgraph/drawio-mcp/issues/29)），
  還有安全性問題（[#12](https://github.com/jgraph/drawio-mcp/issues/12)–[#14](https://github.com/jgraph/drawio-mcp/issues/14)）。
- [#20](https://github.com/jgraph/drawio-mcp/issues/20)：skill 要能自動觸發、選圖表類型、有預設輸出路徑。
  本專案的 SKILL.md 也可以參考這些建議。

## 3. 非 GitHub 社群的回饋（第一版內容）

- **PlantUML：** `goto` 跟泳道一起用會失效，往回的迴圈落在錯的一側
  （[論壇 16520](https://forum.plantuml.net/16520/label-processing-label-together-swimlanes-activity-diagram)、[13006](https://forum.plantuml.net/13006/ability-change-backward-especially-swimlanes-activity-diagram)）。
- **AI 直接畫流程圖不可靠：** 會重疊、每次不同、漏步驟，不會主動問問題
  （[SocietyByte](https://www.societybyte.swiss/en/2026/02/12/why-ai-cant-yet-generate-business-process-diagrams/)、
  [MAO](https://arxiv.org/abs/2408.01916)、[copilot 使用者研究](https://arxiv.org/pdf/2603.12895)）。
- **改一步就要重排整張圖**（[StackExchange](https://webapps.stackexchange.com/questions/39132/in-draw-io-is-there-a-way-to-automatically-position-a-swimlane-or-process-diagr)）。
- **Lucid：** 想要「上方是生命週期階段、下方是角色泳道」；要直向，AI 卻一直給橫向
  （[Lucid 社群](https://community.lucid.co/ideas/use-ai-to-generate-flowcharts-with-swimlanes-7421)）。
- **Visio Data Visualizer 退役：** 從 Excel 產生跨部門流程圖的免費路線沒了
  （[Microsoft](https://techcommunity.microsoft.com/t5/microsoft-365-blog/retirement-of-the-visio-data-visualizer-add-in-for-excel-and/ba-p/4465747)）。
  也有人想把 RACI 嵌進跨部門流程圖（[techcommunity](https://techcommunity.microsoft.com/t5/visio/cross-functional-flowcharts-with-embedded-raci/td-p/1361975)）。
- **ELK partitioning** 不保證泳道內的順序（[ELK](https://eclipse.dev/elk/blog/posts/2023/23-01-09-constraining-the-model.html)）；官方 draw.io MCP 的事後排版靠的就是它。

## 4. 功能比較

✅ 有　△ 部分有　— 沒有　? 未確認

| 功能 | 本專案 | zz-zed | Castaldo | mssoftjp | EW（台灣） | Mermaid swimlane-beta |
|---|---|---|---|---|---|---|
| 版面由程式計算、輸出可重現 | ✅（逐位元組相同） | ✅ | ✅ | ✅ | ✅ | △（隨語系改變，#8759） |
| 畫圖前先檢查流程 | ✅（E/W 訊息碼） | ✅ | ✅ | ✅ | ✅ | — |
| 宣告的回頭迴圈 | ✅ | ✅ | ? | ? | ✅ | △ |
| **階段 / 第二維度** | — | ✅ | ✅ | ? | ✅ | 開發中（PR #8407） |
| **直向泳道** | — | ✅（只有直向） | ? | ✅ | ? | ✅ |
| **保留手動修改** | — | ✅（patch） | — | △（`.flow` 可手改） | ✅（桌面版） | — |
| 可讀性或螢幕預算 | ✅（W202、W209） | △ | — | ✅（1600×900） | ? | — |
| 主題 | ✅ | ? | △ | ? | ? | ✅ |
| 從 .docx 輸入 | ✅ | — | — | — | ✅ | — |
| RACI | — | — | — | — | ✅ | — |
| 痛點、AS-IS / TO-BE | — | — | ✅ | — | △ | — |
| 匯出 BPMN、SVG | — | — | — | SVG、讀 BPMN | ✅ | SVG |
| 中文文件 | ✅ | ✅ | — | — | ✅ | ✅ |
| 安裝方式 | Skill zip、CLI | npx skills、Claude 與 Codex marketplace | Skill | Codex、ChatGPT | ChatGPT plugin | 免安裝 |

## 5. 整理出的需求清單（建議優先度）

| # | 需求 | 依據 | 現況 | 建議 |
|---|---|---|---|---|
| R1 | **階段 / Phase**：跟泳道交叉的欄帶標題 | drawio #3551、#3897；Mermaid #8386、PR #8407；Lucid；4 個競品已經有 | 沒有 | **高，最急**：快要變成基本功能 |
| R2 | **README 加上定位與比較**：跟 Mermaid swimlane-beta、draw.io MCP、同類 skill 的比較表；把逐位元組相同、可讀性預算、標籤擺放寫成賣點 | §1、§4 | 沒有比較 | **高**：成本低 |
| R3 | **生成後保留手動修改**：節點釘選、覆寫順序，或像 zz-zed 那樣做 patch | drawio #5016、bpmn-auto-layout #53、zz-zed | `col` 只能當下限 | **高到中**：設計時要守住「結果可重現」，例如把覆寫寫回 spec |
| R4 | **安裝與發佈**：支援 `npx skills add`、Claude 與 Codex plugin marketplace | zz-zed、mssoftjp、drawio-mcp #20 | 只有 Release zip | 中：成本低、能提高曝光 |
| R5 | **Excel / CSV 流程表輸入** | Visio Data Visualizer 退役；drawio #4121、#520 | 只有文字與 .docx | 中 |
| R6 | **直向泳道** | Lucid；Mermaid 有四種方向；zz-zed 只有直向；mssoftjp 兩種都有 | 只有橫向 | 中 |
| R7 | **向 Mermaid 學的回歸測試**：加標籤不移動節點、不依賴語系排序、自迴圈、空泳道、扁菱形 | §2.1 | 部分未確認 | 中：可以直接轉成測試案例 |
| R8 | **SOP 原文與圖的步驟覆蓋檢查** | AI 漏步驟（MAO、SocietyByte） | lint 只檢查結構 | 中 |
| R9 | **長流程分頁**：子流程、跨頁連接點 | processpiper #15；W202 | 只發警告 | 中 |
| R10 | **額外的語意層**：痛點、工具註記、RACI、人工與自動分色 | Castaldo、EW、ievsantillan、younessili | 有線條樣式，沒有 RACI 或痛點 | 低到中：先挑一項，例如「痛點」或「人工 vs 系統」 |
| R11 | **其他輸出**：BPMN XML、Mermaid `swimlane-beta`、SVG 預覽 | processpiper #13、#37、#46；Mermaid PR #8313 | 只有 .drawio | 低到中；輸出成 Mermaid 能擴大觸及 |

## 6. 限制說明
- GitHub 數字（讚數、留言數、星數）來自 2026-11-14 的搜尋 API 快照。
- 其他 repo 的 issue 是用搜尋 API 讀的；這個 session 不能用 REST API 直接讀那些 repo，所以沒讀到留言串。
- 競品功能是依 README 判斷的，沒有實際跑過。標成 ? 的是 README 沒寫，不代表沒有。
- Reddit 與 Hacker News 的討論串抓不到內容。
