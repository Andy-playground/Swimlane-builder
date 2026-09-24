# 這個工具在幹嘛（白話版）

給人看的入門文。英文說明在 [../README.md](../README.md)，
錯誤碼白話對照在 [CODES-zh.md](CODES-zh.md)。

---

## 一句話

**一份 SOP 文件 → 一張 draw.io 泳道流程圖，而且同樣的輸入永遠畫出一模一樣的圖。**

## 為什麼要做這個

以前畫流程圖是人手拉方框。同一份 SOP 兩個人畫出來不一樣，改一個步驟要重排整張圖，
畫完的圖跟 SOP 文字對不起來也沒人發現。

這工具把「畫」這件事從人手上拿走：人只負責說清楚流程有哪些步驟、誰做、什麼條件分岔；
座標、線怎麼走、框多大，全部由程式算。

---

## 一張圖是怎麼生出來的

四個階段，中間卡著一個 JSON 檔：

```
SOP 文件  ──①抽取──▶  spec.json  ──②檢查──▶  ③算版面  ──④吐 XML──▶  .drawio
         (LLM 做)              (程式做，沒有 AI、不連網)
```

**① 抽取** — 這步是 LLM 做的，規則寫在 [../prompts/extract_spec.md](../prompts/extract_spec.md)。
讀 SOP，判斷「這句話是一個步驟」「這裡是個判斷」「這條線是退回重做」，寫成 spec.json。
這是唯一需要「讀懂人話」的一步，所以交給 AI。

**② 檢查（lint）** — 程式檢查這份 spec 合不合理：線有沒有接到不存在的節點、判斷點是不是
只有一條出路、有沒有繞成沒宣告的圈。有問題就印代碼（見 CODES-zh.md）。

**③ 算版面** — 純數學。決定每個節點在第幾欄、泳道多高、框多寬、線從哪個邊出去。
這一層完全不知道 draw.io 長什麼樣，它只算數字。

**④ 吐 XML** — 把上一步算好的數字翻成 draw.io 看得懂的檔案格式。這一層完全不算數學，
只負責把數字排成 XML。

③ 和 ④ 嚴格分家，是這個 repo 最重要的一條規矩。混在一起的話，改個顏色就可能動到座標。

---

## spec.json 長什麼樣

這是整個工具的核心。看懂它，其他都好說。以 `examples/po-confirmation.spec.json` 為例：

```json
{
  "meta":  { "sop_id": "SOP-001", "title": "Purchase Order Confirmation", "theme": "default" },

  "lanes": [
    { "id": "buyer",    "label": "Buyer Logistics" },
    { "id": "supplier", "label": "Supplier" }
  ],

  "nodes": [
    { "id": "start", "lane": "buyer",    "type": "start",    "label": "PO released" },
    { "id": "t1",    "lane": "supplier", "type": "task",     "label": "Confirm PO in portal" },
    { "id": "d1",    "lane": "buyer",    "type": "decision", "label": "Qty / date match?" }
  ],

  "edges": [
    { "from": "start", "to": "t1", "channel": "system" },
    { "from": "d1",    "to": "t2", "label": "Yes" },
    { "from": "t3",    "to": "d1", "kind": "feedback" }
  ]
}
```

三塊：**誰**（lanes）、**做什麼**（nodes）、**怎麼接**（edges）。

---

## 術語對照

| 名詞 | 白話 |
|---|---|
| **spec** | 那份 JSON 檔。流程的「劇本」，圖是從它算出來的 |
| **lane**（泳道） | 橫的一條，代表一個角色/部門。誰做這步，就放進誰的泳道 |
| **node**（節點） | 圖上一個框。type 六種：`start` 起點、`end` 終點、`task` 步驟、`decision` 判斷、`subprocess` 子流程、`document` 文件 |
| **edge**（連線） | 兩個框之間的箭頭 |
| **col**（欄） | 節點在第幾欄，決定左右位置。程式自己算，你也可以指定——但**指定的是下限**，程式覺得該往後挪還是會挪 |
| **feedback edge** | 回頭線（退回重做）。因為它往回指，會讓流程繞圈，所以一定要標明 `"kind": "feedback"`，否則報 E102 |
| **channel** | 這步在哪裡發生：`system`（系統裡）、`user`（人操作）、`offline`（線下，如 email/電話）。影響線畫成什麼顏色虛實 |
| **step** | SOP 原本的步驟編號（"4a"、"4b"），會印成框上的小徽章 |
| **note** | 節點的補充說明，例外情況的來源寫在這 |
| **theme**（主題） | 一份 JSON，管所有顏色/字體/間距。換 theme 重產就換一套視覺，不用改 spec |
| **golden**（黃金檔） | 存在 repo 裡的「標準答案」.drawio。測試會重產一次跟它逐位元比對——不一樣就表示有東西被改到了 |
| **determinism**（決定性） | 同一份 spec 永遠產出一模一樣的檔案。沒有時間戳、沒有隨機 id。這是 golden 測試能成立的前提 |
| **lint** | 檢查 spec 的那一步，印出 E/W 代碼 |

---

## 日常怎麼用

```bash
python3 swimlane-builder.py lint     myflow.spec.json               # 先檢查
python3 swimlane-builder.py generate myflow.spec.json -o my.drawio  # 再產圖
python3 tests/test_all.py                                     # 改了程式跑這個
```

**一條鐵律：永遠不要手改 `.drawio` 檔。** 要改圖就改 spec 再重產。
手改的東西下次重產就沒了，而且會讓 golden 測試失效。

---

## 已知限制

- 起點／終點圓圈裡的字太長會凸出圓圈，目前沒有錯誤碼會提醒。
- 欄數很多（大約 14 欄以上）的流程，在筆電螢幕上看全圖時字會太小。W209 會提醒，
  但要不要把 SOP 拆成兩張流程，由作者決定——程式不會為了這個自動變形。
