# 交接文件：讓 README 真的有人看（2026-11-14）

給接手的 agent。讀完這份就能繼續工作，不需要重看先前的對話。

## 1. 使用者要什麼

原話整理：
> 現在這個版本可以滿足我 7–8 成的需求。我想改善的是：這個 Repo 現在的功能是什麼、
> 適用於什麼工具、它的功能是什麼、如何從開始到結束。現在的 README 都有寫到，
> 但連我自己都不想看，真的有人會看嗎？

**任務是改寫對外說明，不是加功能。** 讀者要在很短時間內知道四件事：

1. 這是什麼，解決什麼問題（一句話）
2. 可以搭配哪些工具使用（AI 助理、draw.io、命令列）
3. 有哪些功能
4. 從頭到尾怎麼用（拿到 SOP → 拿到圖）

痛點是現在的 README 太長、太像文章，內容都對，但沒人想讀。

## 2. 跟使用者合作的方式

- 用**繁體中文**溝通。repo 對外文件目前是英文 README 加上中文的 `docs/OVERVIEW.md`。
- 使用者兩次拒絕「開 GitHub issue」和「先設計階段（phase）功能」，回答都是「不」。
  **不要再提這兩件事，也不要改程式碼**，除非使用者主動要求。
- 使用者重視內容少而精準。動手大改前先給一個簡短的方向讓他確認，
  例如新 README 的大綱或第一屏的樣子。
- 分支：`claude/magical-volta-et8zvq`。在這個分支上 commit 並 push。不要開 PR，除非使用者要求。
- 使用者沒有說要不要保留英文版。需要時要問：README 改中文、保持英文，還是做成中英兩份。

## 3. 這個 repo 是什麼（事實清單，寫文件時用）

**一句話：** 把 SOP（標準作業程序）轉成 draw.io 泳道圖。AI 只負責讀懂流程；
位置、大小、連線全部由一支 Python 程式計算，同樣輸入每次產出相同的檔案。

**流程（4 步）：**
1. **讀懂（Extract）：** AI 依 `prompts/extract_spec.md` 把 SOP 轉成 JSON spec，內容是 lanes、nodes、edges。
   .docx 先用 `python3 tools/docx2txt.py file.docx` 轉成文字。
2. **檢查（Lint）：** `python3 swimlane-builder.py lint x.spec.json`。
   E 開頭是錯誤，一定要修；W 開頭是建議。訊息碼說明在 `docs/CODES.md` 和 `docs/CODES-zh.md`。
3. **產生（Generate）：** `python3 swimlane-builder.py generate x.spec.json -o x.drawio`。
   一次處理整個資料夾的方式見 `docs/USAGE.md` 的 "Many SOPs at once"。
4. **打開：** 用 draw.io 或 app.diagrams.net 開。不要手改 .drawio，要改就改 spec 再重新產生。

**兩種使用方式：**
- **AI 助理（Skill）：** 從 Releases 下載 `swimlane-builder-skill.zip`，
  上傳到 Claude，或當成檔案交給其他能讀檔、能執行 Python 的 agent。
  `SKILL.md` 規定 AI 先給使用者看一份「抽取摘要」確認，然後只交付 .drawio。
  打包指令是 `python3 tools/build_skill.py`；`.github/workflows/release.yml` 在推 tag `v*` 時自動打包。
- **命令列：** 任何 AI 模型加上 `prompts/extract_spec.md` 產生 spec，再跑 lint 和 generate。

**需求：** Python 3.11 以上，只用標準函式庫，不連網路。

**搭配的工具：** Claude（Skill）、其他能讀檔並執行 Python 的 agent、任何 LLM（只負責抽取）、
draw.io 或 diagrams.net（開檔、編輯、匯出 PNG、PDF、VSDX）。

**功能重點：**
- 版面計算：方框依文字大小調整、連線不穿過方框、標籤放在不會遮到東西的地方
- 同樣輸入產出逐位元組相同的檔案，可以放進 git
- 畫圖前先檢查流程：沒人連到的步驟、只有一個出口的決策、沒宣告的迴圈、太長的標籤
- 主題：`themes/default.json`（draw.io 粉彩）、`themes/classic.json`（黑白）
- 圖例、SOP 原本的步驟編號、三種線條樣式（離線、系統、使用者）
- 範例：`examples/*.spec.json` 和對應的 `.drawio`，共 4 組

**已知限制**（README 末段）：
- 超過約 14 欄，筆電螢幕上就讀不清楚
- 不適合想手動排版的人
- 只畫泳道流程圖，不畫完整 BPMN
- 一些小的繪圖瑕疵

## 4. 現有文件盤點

| 檔案 | 行數 | 內容 | 備註 |
|---|---|---|---|
| `README.md` | 157 | What it is / Why / What you get / Where it fits / How it works（mermaid 圖）/ How to use / Examples / Known limitations / Docs | **要改的主角。** 開頭有 hero 動圖 `docs/media/hero.webp` 和 30 秒影片 `docs/media/swimlane-builder-showreel.mp4` |
| `docs/OVERVIEW.md` | 110 | 中文版介紹、術語對照、已知限制 | 結構跟 README 一樣，問題也一樣 |
| `docs/USAGE.md` | 164 | Try it、Skill、CLI、spec 格式、主題 | 操作細節放在這裡是對的 |
| `docs/CODES.md` / `CODES-zh.md` | 42 / 34 | 訊息碼表 | 不用動 |
| `docs/DEVELOPMENT.md` | 83 | 程式架構、測試、輸出穩定的規則 | 不用動 |
| `SKILL.md` | 88 | 給 AI 的操作指令 | 給機器讀的，不是給人讀的 |

## 5. 先前的研究（可用來寫定位）

完整內容在 `docs/research/2026-11-community-needs.md`（第二版，已 push）。跟 README 有關的重點：

- **Mermaid 從 11.16.0 起有 `swimlane-beta`**（[#2028](https://github.com/mermaid-js/mermaid/issues/2028) 有 401 個讚，2026-06 結案），
  但版面問題很多：加了標籤節點會跑位、版面隨語系改變等。
  讀者第一個問題很可能是「為什麼不用 Mermaid 就好？」，README 要回答。
- **同樣主打「AI 理解流程、程式算版面」的競品**：zz-zed/product-swimlane-drawio、Castaldo-Solutions/process-builder、
  mssoftjp/process-model-generator、pohsuntw-lab/EW-AI-Flowchart（台灣）。
  所以「AI 不碰座標」本身已經不夠獨特。
- **本專案明確的差異：** 逐位元組相同的輸出、螢幕可讀性預算（W202、W209）、標籤擺放、
  可以讀 .docx 與 SOP 流程表的「→ Step N」寫法、主題可以讓一整批 SOP 長得一樣。
- **競品 README 寫得好的地方：**
  - zz-zed 用「直接讓 AI 寫 XML」和「本工具」的對照表，一眼看懂差異
  - Castaldo 是「一小段 JSON → 一張圖」，再加上「30 秒試用」
  - 很多競品都有一行安裝指令（`npx skills add ...`、plugin marketplace）

## 6. 建議做法（還沒跟使用者確認）

1. **先問兩個問題再動手：**
   - 主要讀者是誰：寫 SOP 的業務人員、還是會用 AI 或命令列的技術人員？
   - README 用哪種語言？
2. **讓 README 第一屏就回答四件事**，目標是捲動一次內看完：
   - 一句話說明加 hero 圖
   - 「搭配什麼工具」：一個小表格或一排標籤，例如 Claude Skill／任何 LLM＋CLI／draw.io
   - 「從頭到尾」：3–4 步，每步一行，例如 SOP → AI 讀懂並給你確認摘要 → 自動檢查與排版 → .drawio
   - 「30 秒試用」：一行指令加上一個範例
3. **其餘內容往下放或移到 docs：** Why、Where it fits、完整功能列表、限制、比較表
   （包含「為什麼不用 Mermaid 或直接讓 AI 畫」）。README 只留連結。
4. `docs/OVERVIEW.md`（中文）用同樣結構改寫，或改成中文版 README。
5. 改完自己用「30 秒能不能看懂」的標準檢查一次，再請使用者看。

## 7. 待確認

- 第 6 步的兩個問題：讀者是誰、用哪種語言。
- 要不要加安裝管道，例如 `npx skills add`。這屬於功能，要使用者同意才做。
- README 的 hero 圖與影片要不要保留在最上方。
